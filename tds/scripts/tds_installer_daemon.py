"""
Daemon to do installs. It checks the database to see what deployments it needs
to do, does them, and updates the database.
"""

from datetime import datetime, timedelta
from multiprocessing import Process

from simpledaemon import Daemon

import tagopsdb
import tds.deploy_strategy
import tds.exceptions
import tds.model

from tds.apps.base import TDSProgramBase


class TDSInstallerDaemon(Daemon, TDSProgramBase):
    """
    Thing to do the thing.
    """

    def __init__(self, *args, **kwargs):
        """
        Determine deployment strategy and initialize several parameters
        """

        # ongoing_deployments is a list with items of form:
        # (deployment_entry, process_doing_deployment,
        #  time_of_deployment_start)
        self.ongoing_deployments = list()
        self.retry = kwargs.pop('retry') if 'retry' in kwargs else 4
        self.threshold = kwargs.pop('threshold') if 'threshold' in kwargs \
            else timedelta(minutes=5)

        super(TDSInstallerDaemon, self).__init__(*args, **kwargs)

        self.create_deploy_strategy(
            self.config.get('deploy_strategy', 'salt')
        )

    def create_deploy_strategy(self, deploy_strat_name):
        if deploy_strat_name == 'mco':
            cls = tds.deploy_strategy.TDSMCODeployStrategy
        elif deploy_strat_name == 'salt':
            cls = tds.deploy_strategy.TDSSaltDeployStrategy
        else:
            raise tds.exceptions.ConfigurationError(
                'Invalid deploy strategy: %r', deploy_strat_name
            )

        self._deploy_strategy = cls(
            **self.config.get(deploy_strat_name, {})
        )

    @property
    def deploy_strategy(self):
        """
        Accessor for the DeployStrategy instance used by this object.
        """

        return self._deploy_strategy

    def find_deployments(self):
        """
        Find host and tier deployments with status == 'queued'.
        Returns the tuple that was appended to ongoing_deployments, False
        otherwise.
        """

        deps = tds.model.Deployment.find(started=False)

        if deps:
            deployment = deps[0]
            deployment_process = Process(
                target=self.do_serial_deployment,
                args=(deployment,),
            )
            tup = (
                deployment,
                deployment_process,
                datetime.now(),
            )
            self.ongoing_deployments.append(tup)

            return tup

        return False

    def get_stalled_deployments(self):
        """
        Return the list of ongoing deployments that were started more than
        self.threshold ago.
        """

        return [dep for dep in self.ongoing_deployments
                if datetime.now() > dep[2] + self.threshold]

    def _do_host_deployment(self, host_deployment):
        """
        Perform host deployment for given host and update database
        with results.
        """

        # If host already has a valid deployment, nothing to do
        if host_deployment.status == 'ok':
            return

        success, host_result = self.deploy_strategy.deploy_to_host(
            host_deployment.host.name,
            host_deployment.deployment.package.name,
            host_deployment.deployment.package.version,
            retry=self.retry
        )

        if success:
            host_deployment.status = 'ok'
        else:
            host_deployment.status = 'failed'

        host_deployment.deploy_result = host_result
        tagopsdb.Session.commit()

        return host_deployment.status

    def _do_tier_deployment(self, tier_deployment):
        """
        Perform tier deployment for given tier (only doing hosts that
        require the deployment) and update database with results.
        """

        dep_hosts = sorted(
            tier_deployment.application.hosts,
            key=lambda host: host.name,
        )
        tier_state = []

        for dep_host in dep_hosts:
            host_deployment = tds.model.HostDeployment.find(host=dep_host)
            tier_state.append(self._do_host_deployment(host_deployment))

        if 'failed' in tier_state:
            tier_deployment.status = 'incomplete'
        else:
            tier_deployment.status = 'complete'

        tagopsdb.Session.commit()

    def do_serial_deployment(self, deployment):
        """
        Perform deployments for tier or host(s) one host at a time
        (no parallelism).
        """

        tier_deployments = deployment.app_deployments

        if tier_deployments:
            for tier_deployment in tier_deployments:
                self._do_tier_deployment(tier_deployment)
        else:
            host_deployments = sorted(
                deployment.host_deployments,
                key=lambda host_dep: host_dep.host.name,
            )

            for host_deployment in host_deployments:
                self._do_host_deployment(host_deployment)
