"""
Controller for 'deploy' commands.
"""
import collections
import progressbar
import itertools
import time
import warnings
from datetime import datetime, timedelta

import tagopsdb
import tagopsdb.exceptions
import tagopsdb.deploy.repo
import tagopsdb.deploy.deploy
import tagopsdb.deploy.package

import tds.model
import tds.utils
import tds.notifications
import tds.deploy_strategy

import logging

from .base import BaseController, validate as input_validate

log = logging.getLogger('tds')


def create_deployment(project, hosts, apptypes, **params):
    """Translate the common "params" argument into a Deployment instance."""
    return tds.model.Deployment(
        actor=tds.model.Actor(
            name=params.get('user'),
            groups=params.get('groups'),
        ),
        action=dict(
            command=params.get('command_name'),
            subcommand=params.get('subcommand_name'),
        ),
        project=project,
        package=tds.model.Package(
            name=params.get('package_name'),
            version=params.get('version'),
        ),
        target=dict(
            env=params.get('env'),
            apptypes=apptypes,
            hosts=hosts,
        ),
    )


class DeployController(BaseController):

    """Commands to manage deployments for supported applications."""

    dep_types = {'promote': 'Deployment',
                 'redeploy': 'Redeployment',
                 'rollback': 'Rollback',
                 'push': 'Push',
                 'repush': 'Repush',
                 'revert': 'Reversion', }
    envs = {'dev': 'development',
            'stage': 'staging',
            'prod': 'production', }
    env_order = ['dev', 'stage', 'prod']

    requires_tier_progression = True

    access_levels = {
        'add_apptype': 'admin',
        'delete_apptype': 'admin',
        'invalidate': 'environment',
        'show': 'environment',
        'validate': 'environment',
        'promote': 'environment',
        'redeploy': 'environment',
        'rollback': 'environment',
        'restart': 'environment',
    }

    def __init__(self, config):
        """Basic initialization"""
        super(DeployController, self).__init__(config)
        self._deploy_strategy = tds.deploy_strategy.TDSMCODeployStrategy(
            mco_bin=self.app_config['mco']['bin']
        )

    @property
    def deploy_strategy(self):
        """
        Accessor for the DeployStrategy instance used by this object.
        """
        return self._deploy_strategy

    @tds.utils.debug
    def check_previous_environment(self, project, params, package, apptype):
        """Ensure deployment for previous environment for given package
           and apptier was validated; this is only relevant for staging
           and production environments.
        """
        # Note: this will currently allow any user to force
        # a deployment without previous tier requirement;
        # the use of '--force' needs to be authorized further up

        if not self.requires_tier_progression or params['force']:
            log.debug(
                'Previous environment not required for %r or "--force" '
                'option in use',
                project.name
            )
            return True

        log.debug('Checking for validation in previous environment')

        if params['env'] != 'dev':
            prev_env = self.get_previous_environment(params['env'])
            log.log(5, 'Previous environment is: %s', prev_env)

            prev_deps = tagopsdb.deploy.deploy.find_app_deployment(
                package.id,
                [apptype.id],
                self.envs[prev_env]
            )
            # There might be no deployment available; otherwise
            # there should only be one deployment here
            if not prev_deps:
                raise tds.exceptions.TDSException(
                    'Package "%s@%s" never validated in "%s" environment for '
                    'target "%s"',
                    project.name, params['version'],
                    prev_env, apptype.name
                )

            prev_app_dep, prev_app_type, prev_dep_type, \
                prev_pkg = prev_deps[0]
            log.log(5, 'Previous application deployment is: %r',
                    prev_app_dep)
            log.log(5, 'Previous application type is: %s',
                    prev_app_type)
            log.log(5, 'Previous deployment type is: %s',
                    prev_dep_type)
            log.log(5, 'Previous package is: %r', prev_pkg)

            if (prev_dep_type != 'deploy' or
                    prev_app_dep.status != 'validated'):
                log.info(
                    'Application %r with version %r not fully '
                    'deployed or validated to previous environment '
                    '(%s) for apptype %r', project.name,
                    params['version'], prev_env, prev_app_type
                )
                return False

        log.log(5, 'In development environment, nothing to check')

        return True

    @tds.utils.debug
    def check_for_current_deployment(self, params, apptype, hosts=None):
        """For the current app type, see if there are any current
           deployments running and notify if there is.
        """

        log.debug(
            'Checking for a deployment of the same application '
            'already in progress'
        )

        time_delta = timedelta(hours=1)  # Harcoded to an hour for now
        log.log(5, 'time_delta is: %s', time_delta)

        dep = {}

        dep['info'] = tagopsdb.deploy.deploy.find_running_deployment(
            apptype.id,
            self.envs[params['env']],
            hosts=[x.name for x in hosts] if hosts else None
        )

        if dep['info']:
            log.debug('Current deployment found')

            dep['type'], data = dep['info']
            log.log(5, 'Deployment type is: %s', dep['type'])

            if dep['type'] == 'tier':
                dep['user'], dep['realized'], dep['env'], dep['apptype'] = \
                    data
                log.log(5, 'Deployment user is: %s', dep['user'])
                log.log(5, 'Deployment realized is: %s', dep['realized'])
                log.log(5, 'Deployment environment is: %s', dep['env'])
                log.log(5, 'Deployment apptype is: %s', dep['apptype'])

                if datetime.now() - dep['realized'] < time_delta:
                    log.info(
                        'User "%s" is currently running a '
                        'deployment for the %s app tier in the %s '
                        'environment, skipping...',
                        dep['user'], dep['apptype'], dep['env']
                    )
                    return True
            else:   # dep['type'] is 'host'
                dep['hosts'] = []

                for entry in data:
                    dep['user'], dep['realized'], dep['hostname'], \
                        dep['env'] = entry
                    log.log(5, 'Deployment user is: %s', dep['user'])
                    log.log(5, 'Deployment realized is: %s', dep['realized'])
                    log.log(5, 'Deployment hostname is: %s', dep['hostname'])
                    log.log(5, 'Deployment environment is: %s', dep['env'])

                    if datetime.now() - dep['realized'] < time_delta:
                        log.log(
                            5, 'Host %r active with deployment',
                            dep['hostname']
                        )
                        dep['hosts'].append(dep['hostname'])

                if dep['hosts']:
                    # Allow separate hosts to get simultaneous deployments
                    if (hosts is None or
                            not set(dep['hosts']).isdisjoint(set(hosts))):
                        log.info(
                            'User "%s" is currently running a '
                            'deployment for the hosts "%s" in '
                            'the %s environment, skipping...',
                            dep['user'], ', '.join(dep['hosts']), dep['env']
                        )
                        return True

        log.debug('No current deployment found')
        return False

    @tds.utils.debug
    def check_tier_state(self, params, pkg, app_dep):
        """Ensure state of tier (from given app deployment) is consistent
           with state and deployment package versions.
        """

        log.debug('Checking state of tier')

        apptype_hosts = tagopsdb.deploy.deploy.find_hosts_for_app(
            app_dep.app_id,
            self.envs[params['env']]
        )
        apptype_hostnames = [x.hostname for x in apptype_hosts]
        log.log(5, 'Tier hosts are: %s', ', '.join(apptype_hostnames))

        dep_hosts = \
            tagopsdb.deploy.deploy.find_host_deployments_by_package_name(
                pkg.pkg_name,
                apptype_hostnames
            )
        dep_hostnames = [x.hostname for x in dep_hosts]

        if dep_hostnames:
            log.log(5, 'Deployed hosts are: %s', ', '.join(dep_hostnames))

        missing_deps = list(set(apptype_hostnames) - set(dep_hostnames))
        version_diffs = [x.hostname for x in dep_hosts
                         if x.version != params['version']]

        if version_diffs:
            log.log(5, 'Version differences on: %s', ', '.join(version_diffs))

        not_ok_hosts = tagopsdb.deploy.deploy.find_host_deployments_not_ok(
            pkg.id,
            app_dep.app_id,
            self.envs[params['env']]
        )
        not_ok_hostnames = [x.hostname for x in not_ok_hosts]

        if not_ok_hostnames:
            log.log(
                5, 'Hosts with failed deployments are: %s',
                ', '.join(not_ok_hostnames)
            )

        if missing_deps or version_diffs or not_ok_hosts:
            return ('failed', missing_deps, version_diffs, not_ok_hostnames)
        else:
            return ('ok', [], [], [])

    @tds.utils.debug
    def deploy_to_host(self, dep_host, app, version, retry=4):
        """Deploy specified package to a given host."""

        return self.deploy_strategy.deploy_to_host(
            dep_host,
            app,
            version,
            retry
        )

    @tds.utils.debug
    def restart_host(self, dep_host, app, retry=4):
        """Restart a host."""
        return self.deploy_strategy.restart_host(dep_host, app, retry)

    @tds.utils.debug
    def deploy_to_hosts(self, project, params, dep_hosts, dep, redeploy=False):
        """Perform deployment on given set of hosts (only doing those
           that previously failed with a redeploy).
        """

        log.debug('Performing host deployments')

        total_hosts = len(dep_hosts)
        host_count = 1
        failed_hosts = []

        # widgets for progress bar
        widgets = ['Completed: ', progressbar.Counter(),
                   ' out of %d hosts' % total_hosts,
                   ' (', progressbar.Timer(), ', ', progressbar.ETA(), ')']

        if params.get('verbose', None) is None:
            pbar = progressbar.ProgressBar(widgets=widgets,
                                           maxval=total_hosts).start()

        for dep_host in sorted(dep_hosts, key=lambda host: host.hostname):
            pkg = dep.package
            app, version = pkg.pkg_name, pkg.version
            log.log(5, 'Project name and version: %s %s', app, version)

            host_dep = tagopsdb.deploy.deploy.find_host_deployment_by_depid(
                dep.id,
                dep_host.hostname
            )

            if redeploy and host_dep and host_dep.status != 'ok':
                log.log(5, 'Host %r needs redeloyment', dep_host.hostname)
                success, info = self.deploy_to_host(
                    dep_host.hostname, app, version
                )

                if success:
                    log.log(
                        5, 'Deployment to host %r successful',
                        dep_host.hostname
                    )

                    # Commit to DB immediately
                    host_dep.status = 'ok'
                    tagopsdb.Session.commit()

                    log.log(5, 'Committed database (nested) change')
                else:
                    log.log(
                        5, 'Deployment to host %r failed',
                        dep_host.hostname
                    )
                    failed_hosts.append((dep_host.hostname, info))
            else:
                if host_dep and host_dep.status == 'ok':
                    log.info(
                        'Host "%s" already has "%s@%s" successfully '
                        'deployed, skipping',
                        dep_host.hostname, app, version
                    )
                    continue

                # Clear out any old deployments for this host
                log.log(
                    5, 'Deleting any old deployments for host %r',
                    dep_host.hostname
                )
                tagopsdb.deploy.deploy.delete_host_deployment(
                    dep_host.hostname,
                    project.name
                )
                host_dep = tagopsdb.deploy.deploy.add_host_deployment(
                    dep.id,
                    dep_host.id,
                    params['user'],
                    'inprogress'
                )
                success, info = self.deploy_to_host(dep_host.hostname, app,
                                                    version)

                if success:
                    log.log(
                        5, 'Deployment to host %r successful',
                        dep_host.hostname
                    )

                    # Commit to DB immediately
                    host_dep.status = 'ok'
                    tagopsdb.Session.commit()
                else:
                    log.log(
                        5, 'Deployment to host %r failed', dep_host.hostname
                    )

                    # Commit to DB immediately
                    host_dep.status = 'failed'
                    tagopsdb.Session.commit()

                    failed_hosts.append((dep_host.hostname, info))

                log.log(5, 'Committed database (nested) change')

            if params.get('verbose', None) is None:
                pbar.update(host_count)

            host_count += 1

            delay = params.get('delay', None)
            if delay is not None:
                log.log(5, 'Sleeping for %d seconds...', delay)
                time.sleep(delay)

        if params.get('verbose', None) is None:
            pbar.finish()

        # If any hosts failed, show failure information for each
        if failed_hosts:
            log.info('Some hosts had failures:\n')

            for failed_host, reason in failed_hosts:
                log.info('-----')
                log.info('Hostname: %s', failed_host)
                log.info('Reason: %s', reason)

            return False
        else:
            return True

    @tds.utils.debug
    def deploy_to_hosts_or_tiers(self, project, hosts, apptypes, params, dep,
                                 app_dep_map, app_host_map, redeploy=False,
                                 rollback=False):
        """Do the deployment to the requested hosts or application tiers"""

        log.debug('Deploying to requested hosts or application tiers')

        if hosts:
            log.log(5, 'Deployment is for hosts...')
            for apptype in list(apptypes):
                apphosts = app_host_map.get(apptype.id, None)
                if apphosts is None:
                    continue

                if self.check_for_current_deployment(params, apptype,
                                                     hosts=apphosts):
                    log.log(
                        5, 'App %s already has deployment, skipping...',
                        apptype
                    )
                    apptypes.remove(apptype)
                    app_host_map.pop(apptype.id)
                    continue

                log.log(5, 'Hosts being deployed to are: %r', apphosts)

                deploy_result = self.deploy_to_hosts(
                    project, params, apphosts, dep, redeploy=redeploy
                )

                # We want the tier status updated only if doing
                # a rollback
                if deploy_result and rollback:
                    app_dep = app_dep_map[apptype.id][0]
                    app_dep.status = 'complete'
        else:
            log.log(5, 'Deployment is for application tiers...')

            for apptype in list(apptypes):
                if apptype.id not in app_dep_map:
                    continue
                if self.check_for_current_deployment(params, apptype):
                    log.log(
                        5, 'App %s already has deployment, skipping...',
                        apptype
                    )
                    apptypes.remove(apptype)
                    app_dep_map.pop(apptype.id)
                    continue

                if redeploy:
                    dep_info = app_dep_map.get(apptype.id, None)
                    app_dep, app_type, _dep_type, pkg = dep_info

                    # Don't redeploy to a validated tier
                    if app_dep.status == 'validated':
                        log.info(
                            'Application "%s" with version "%s" '
                            'already validated on app type %s"',
                            project.name, pkg.version,
                            app_type
                        )
                        continue
                else:
                    app_dep = tagopsdb.deploy.deploy.add_app_deployment(
                        dep.id,
                        apptype.id,
                        params['user'],
                        'inprogress',
                        self.envs[params['env']]
                    )

                try:
                    dep_hosts = tagopsdb.deploy.deploy.find_hosts_for_app(
                        apptype.id,
                        self.envs[params['env']]
                    )
                except tagopsdb.exceptions.DeployException:
                    log.info(
                        'No hosts available for application type '
                        '"%s" in %s environment',
                        apptype.name, self.envs[params['env']]
                    )

                    # Set the deployment status due to no hosts
                    # being available
                    app_dep.status = 'incomplete'
                    log.log(
                        5, 'Setting deployment status to: %s', app_dep.status
                    )
                    continue

                if self.deploy_to_hosts(project, params, dep_hosts, dep,
                                        redeploy=redeploy):
                    app_dep.status = 'complete'
                else:
                    app_dep.status = 'incomplete'

                log.log(5, 'Setting deployment status to: %s', app_dep.status)

        if params['env'] == 'prod':
            log.info(
                'Please review the following Nagios group views '
                'or the deploy health status:'
            )

            for apptype in apptypes:
                log.info(
                    '  https://nagios.tagged.com/nagios/cgi-bin/'
                    'status.cgi?style=detail&hostgroup=app.%s', apptype.name
                )

    def determine_invalidations(self, project, params, apptypes, app_dep_map):
        """Determine which application tiers need invalidations performed"""

        log.debug(
            'Determining invalidations for requested application types'
        )

        curr_deps = tagopsdb.deploy.deploy.find_latest_deployed_version(
            project.name,
            self.envs[params['env']],
            apptier=True
        )
        curr_dep_versions = {}

        for app_type, version, revision in curr_deps:
            log.log(
                5, 'App type: %s, Version: %s, Revision %s',
                app_type, version, revision
            )
            curr_dep_versions[app_type] = int(version)

        for apptype in apptypes:
            if not app_dep_map[apptype.id]:
                log.log(
                    5, 'Application ID %r is not in deployment/'
                    'application map', apptype.id
                )
                continue

            valid = True

            app_dep, app_type, dep_type, pkg = app_dep_map[apptype.id]
            log.log(5, 'Application deployment is: %r', app_dep)
            log.log(5, 'Application type is: %s', app_type)
            log.log(5, 'Deployment type is: %s', dep_type)
            log.log(5, 'Package is: %r', pkg)

            # Ensure version to invalidate isn't the current
            # deployment for this app type
            if curr_dep_versions.get(app_type, None) == params['version']:
                log.info(
                    'Unable to invalidate application "%s" with '
                    'version "%s" for apptype "%s" as that version '
                    'is currently deployed for the apptype',
                    project.name, params['version'], app_type
                )
                valid = False

            if valid:
                if app_dep.status != 'validated':
                    raise tds.exceptions.TDSException(
                        'Package "%s@%s" currently deployed on target "%s"',
                        pkg.name, pkg.version, app_type
                    )

            if not valid:
                log.log(
                    5, 'Deleting application ID %r from '
                    'deployment/application map', apptype.id
                )
                del app_dep_map[apptype.id]

        log.log(5, 'Deployment/application map is: %r', app_dep_map)

        return app_dep_map

    @tds.utils.debug
    def determine_new_deployments(self, project, hosts, apptypes, params,
                                  package, app_host_map, app_dep_map):
        """Determine which application tiers or hosts need new deployments"""

        log.debug(
            'Determining deployments for requested application '
            'types or hosts'
        )

        # For each app type, do the following:
        #   1. If app type does haven't a current deployment, check next
        #   2. For non-development environments, ensure the previous
        #      environment has a validated instance of the requested
        #      version of the application
        #   3. If step 2 is okay, check if the requested version of
        #      the application is already deployed and not invalidated
        #   4. If either step 2 or 3 failed, remove host/app type from
        #      relevant mapping to be used for deployments
        for apptype in apptypes:
            valid = self.check_previous_environment(
                project, params, package, apptype
            )

            if valid:
                if not app_dep_map[apptype.id]:
                    log.log(
                        5, 'Application %r is not in '
                        'deployment/application map', apptype
                    )
                    continue

                app_dep, app_type, dep_type, pkg = app_dep_map[apptype.id]
                log.log(5, 'Application deployment is: %r', app_dep)
                log.log(5, 'Application type is: %s', app_type)
                log.log(5, 'Deployment type is: %s', dep_type)
                log.log(5, 'Package is: %r', pkg)

                if (app_dep.status != 'invalidated' and dep_type == 'deploy'
                        and pkg.version == params['version']):
                    log.info(
                        'Application "%s" with version "%s" '
                        'already deployed to this environment (%s) '
                        'for apptype "%s"',
                        project.name, params['version'],
                        self.envs[params['env']], app_type
                    )
                    valid = False

            if not valid:
                if app_host_map:
                    log.log(
                        5, 'Deleting application %r from '
                        'host/application map', apptype
                    )
                    del app_host_map[apptype.id]
                else:
                    log.log(
                        5, 'Deleting application %r from '
                        'deployment/application map', apptype
                    )
                    del app_dep_map[apptype.id]

        log.log(5, 'Host/application map is: %r', app_host_map)
        log.log(5, 'Deployment/application map is: %r', app_dep_map)

        return (app_host_map, app_dep_map)

    @tds.utils.debug
    def determine_rollbacks(self, hosts, apptypes, params, app_host_map,
                            app_dep_map):
        """Determine which application tiers or hosts need rollbacks"""

        log.debug('Determining rollbacks for requested application types')

        app_pkg_map = {}

        for apptype in apptypes:
            if app_dep_map.get(apptype.id, None) is None:
                log.log(
                    5, 'Application %r is not in '
                    'deployment/application map', apptype
                )
                continue

            valid = True

            _app_dep, app_name, _dep_type, package = app_dep_map[apptype.id]

            pkg_def = package.package_definition

            if hosts:
                prev_dep_info = \
                    tagopsdb.deploy.deploy.find_latest_validated_deployment(
                        pkg_def.name, apptype.id,
                        self.envs[params['env']])
            else:
                prev_dep_info = \
                    tagopsdb.deploy.deploy.find_previous_validated_deployment(
                        pkg_def.name, apptype.id,
                        self.envs[params['env']])

            if prev_dep_info is None:
                log.info(
                    'No previous deployment to roll back to for '
                    'application "%s" for app type "%s" in %s '
                    'environment', pkg_def.name, app_name,
                    self.envs[params['env']]
                )
                valid = False
            else:
                prev_app_dep, prev_pkg_id = prev_dep_info
                log.log(
                    5, 'Previous application deployment is: %r',
                    prev_app_dep
                )
                log.log(5, 'Previous package ID is: %s', prev_pkg_id)

                app_pkg_map[apptype.id] = prev_pkg_id

            if not valid:
                log.log(
                    5, 'Deleting application %r from '
                    'deployment/application map', apptype
                )
                del app_dep_map[apptype.id]

        log.log(5, 'Package/application map is: %r', app_pkg_map)
        log.log(5, 'Host/application map is: %r', app_host_map)
        log.log(5, 'Deployment/application map is: %r', app_dep_map)

        return (app_pkg_map, app_host_map, app_dep_map)

    @tds.utils.debug
    def determine_validations(self, project, params, apptypes,
                              app_dep_map):
        """Determine which application tiers need validation performed"""

        for apptype in apptypes:
            if not app_dep_map[apptype.id]:
                log.log(
                    5, 'Application ID %r is not in '
                    'deployment/application map', apptype.id
                )
                continue

            valid = True

            app_dep, app_type, dep_type, pkg = app_dep_map[apptype.id]
            log.log(5, 'Application deployment is: %r', app_dep)
            log.log(5, 'Application type is: %s', app_type)
            log.log(5, 'Deployment type is: %s', dep_type)
            log.log(5, 'Package is: %r', pkg)

            if app_dep.status == 'validated':
                log.info(
                    'Deployment for application %r for apptype %r '
                    'already validated in %s environment',
                    project.name, app_type,
                    self.envs[params['env']]
                )
                valid = False

            if valid:
                # Ensure tier state is consistent
                result, missing, diffs, not_ok_hostnames = \
                    self.check_tier_state(params, pkg, app_dep)

                if result != 'ok':
                    log.info(
                        'Encountered issues while validating '
                        'version %r of application %r:',
                        params['version'], project.name
                    )

                    if missing:
                        log.info(
                            '  Hosts missing deployments of given version:'
                        )
                        log.info('    %s', ', '.join(missing))

                    if diffs:
                        log.info(
                            '  Hosts with different versions than '
                            'the one being validated:'
                        )
                        log.info('    %s', ', '.join(diffs))

                    if not_ok_hostnames:
                        log.info('  Hosts not in an "ok" state:')
                        log.info('    %s', ', '.join(not_ok_hostnames))

                    if params['force']:
                        log.info(
                            'The "--force" option was used, '
                            'validating regardless'
                        )
                        valid = True
                    else:
                        log.info(
                            'Rejecting validation, please use '
                            '"--force" if you still want to validate'
                        )
                        valid = False

            if not valid:
                log.log(
                    5, 'Deleting application ID %r from '
                    'deployment/application map', apptype.id
                )
                del app_dep_map[apptype.id]

        log.log(5, 'Deployment/application map is: %r', app_dep_map)

        return app_dep_map

    @tds.utils.debug
    def ensure_newer_versions(self, project, params):
        """Ensure version being deployed is more recent than
           the currently deployed versions on requested app types
        """

        log.debug(
            'Ensuring version to deploy is newer than the '
            'currently deployed version'
        )

        newer_versions = []
        dep_versions = tagopsdb.deploy.deploy.find_latest_deployed_version(
            project.name,
            self.envs[params['env']],
            apptier=True
        )

        for dep_app_type, dep_version, dep_revision in dep_versions:
            if params['apptypes'] and dep_app_type not in params['apptypes']:
                continue

            log.log(
                5, 'Deployment application type is: %s',
                dep_app_type
            )
            log.log(5, 'Deployment version is: %s', dep_version)
            log.log(5, 'Deployment revision is: %s', dep_revision)

            # Currently not using revision (always '1' at the moment)
            # 'dep_version' must be typecast to an integer as well,
            # since the DB stores it as a string - may move away from
            # integers for versions in the future, so take note here
            warnings.warn(
                'Package versions are being compared with string semantics'
            )
            if params['version'] < dep_version:
                log.log(
                    5, 'Deployment version %r is newer than '
                    'requested version %r', dep_version,
                    params['version']
                )
                newer_versions.append(dep_app_type)

        if newer_versions:
            app_type_list = ', '.join(['"%s"' % x for x in newer_versions])
            log.info(
                'Application %r for app types %s have newer '
                'versions deployed than the requested version %r',
                project.name, app_type_list, params['version']
            )
            return False

        return True

    @tds.utils.debug
    def find_app_deployments(self, package, apptypes, params):
        """Find all relevant application deployments for the requested
        app types and create an application/deployment mapping,
        keeping track of which app types have a current deployment
        and which don't
        """

        log.debug('Finding all relevant application deployments')

        environment = tagopsdb.Environment.get(
            environment=self.envs[params['env']]
        )

        app_deployments = {}

        for app in apptypes:
            app_deployments[app.id] = None

            for app_dep in reversed(app.app_deployments):
                if app_dep.environment_obj != environment:
                    continue
                if app_dep.deployment.package != package:
                    continue

                app_deployments[app.id] = (
                    app_dep, app.name, app_dep.deployment.type, package
                )
                break

        return app_deployments

    @tds.utils.debug
    def get_app_info(self, project, hosts, apptypes, params, hostonly=False):
        """Verify requested package and which hosts or app tiers
        to install the package; for hosts a mapping is kept between
        them and their related app types
        """

        log.debug(
            'Verifying requested package is correct for given '
            'application tiers or hosts'
        )

        if hosts:
            log.log(5, 'Verification is for hosts...')

            pkg, app_host_map = self.verify_package(
                project, hosts, apptypes, params, hostonly=hostonly
            )

            host_deps = \
                tagopsdb.deploy.deploy.find_host_deployments_by_package_name(
                    project.name,
                    [x.name for x in hosts]
                )

            for host_dep, hostname, app_id, dep_version in host_deps:
                log.log(5, 'Host deployment is: %r', host_dep)
                log.log(5, 'Hostname is: %s', hostname)
                log.log(5, 'Application ID is: %s', app_id)
                log.log(5, 'Deployment version is: %s', dep_version)

                curr_version = params.get('version', dep_version)
                log.log(5, 'Current version is: %s', curr_version)

                if (params['subcommand_name'] != 'rollback'
                    and dep_version == curr_version
                        and host_dep.status == 'ok' and params['deployment']):
                    log.info(
                        'Project %r with version %r already '
                        'deployed to host %r', project.name,
                        curr_version, hostname
                    )
                    app_host_map[app_id].remove(hostname)

                    if not app_host_map[app_id]:
                        log.log(
                            5, 'Application ID %r is not in '
                            'host/application map', app_id
                        )
                        del app_host_map[app_id]

            apptypes = [app_host_map[k][0].application for k in app_host_map]
        else:
            log.log(5, 'Verification is for application tiers...')

            pkg, apptypes = self.verify_package(
                project, hosts, apptypes, params
            )

            app_host_map = None   # No need for this for tiers

        log.log(5, 'Package ID is: %s', pkg.id)
        log.log(
            5, 'Application IDs are: %s',
            ', '.join([str(x.id) for x in apptypes])
        )
        log.log(5, 'Host/application map is: %r', app_host_map)

        return (pkg, apptypes, app_host_map)

    @tds.utils.debug
    def get_package(self, project, params, hostonly=False):
        """Get the package ID for the current project and version
           (or most recent deployed version if none is given) for
           a given set of application types
        """

        log.debug('Determining package ID for given project')

        app_types = map(
            tagopsdb.deploy.deploy.find_apptype_by_appid,
            [x.id for x in project.targets]
        )
        log.log(5, 'Application types are: %s', ', '.join(app_types))

        if 'version' in params:
            log.log(5, 'Using given version %r for package', params['version'])
            version = params['version']
        else:
            log.log(5, 'Determining version for package')

            # Must determine latest deployed version(s);
            # they must all use the same package version
            # (Tuple of app_type, version, revision returned
            #  with DB query)
            apptier = not hostonly

            package_defs = [
                x.package_definition
                for target in project.targets
                for x in tagopsdb.ProjectPackage.find(
                    project_id=project.id, app_id=target.id
                )
            ]

            assert len(package_defs) == len(project.targets)

            last_deps = sum([
                tagopsdb.deploy.deploy.find_latest_deployed_version(
                    pkg_def.name,
                    self.envs[params['env']],
                    apptier=apptier
                ) for pkg_def in package_defs],
                []
            )

            log.log(5, 'Latest validated deployments: %r', last_deps)

            if hostonly:
                versions = [x.version for x in last_deps
                            if x.app_id in [t.id for t in project.targets]]
            else:
                versions = [x.version for x in last_deps
                            if x.appType in app_types]

            log.log(5, 'Found versions are: %s', ', '.join(versions))

            if not versions:
                log.info(
                    'Project "%s" has no current tier/host '
                    'deployments to verify for the given apptypes/'
                    'hosts', project.name
                )
                raise SystemExit(1)

            if not all(x == versions[0] for x in versions):
                raise ValueError('Multiple versions not allowed')

            version = versions[0]
            log.log(5, 'Determined version is: %s', version)
            params['current_version'] = version   # Used for notifications

        # Revision hardcoded to '1' for now
        pkg = tagopsdb.deploy.package.find_package(
            project.name,
            version,
            '1'
        )

        if pkg is None:
            raise tds.exceptions.NotFoundError(
                'Package "%s@%s" does not exist',
                project.name,
                version
            )

        return pkg

    @tds.utils.debug
    def get_previous_environment(self, curr_env):
        """Find the previous environment to the current one"""

        log.debug('Determining previous deployment environment')

        # Done this way since negative indexes are allowed
        if curr_env == 'dev':
            raise tds.exceptions.WrongEnvironmentError(
                'There is no environment before the current environment (%s)',
                curr_env
            )

        try:
            return self.env_order[self.env_order.index(curr_env) - 1]
        except ValueError:
            raise tds.exceptions.WrongEnvironmentError(
                'Invalid environment: %s', curr_env
            )

    @tds.utils.debug
    def perform_deployments(self, project, hosts, apptypes, package, params,
                            app_dep_map, app_host_map):
        """Perform all deployments to the requested application tiers or
           hosts
        """

        log.debug('Performing deployments to application tiers or hosts')

        # All is well, now do the deployment
        #   1. See if a deployment entry already exists in DB and use it,
        #      otherwise create a new one
        #   2. If deploying to tier, add an app deployment entry in DB
        #   3. Determine the appropriate hosts to deploy the application
        #   4. Do the deploy to the hosts
        dep = None
        pkg_deps = tagopsdb.deploy.deploy.find_deployment_by_pkgid(package.id)

        if pkg_deps:
            log.log(5, 'Found existing deployment')

            last_pkg_dep = pkg_deps[0]
            log.log(5, 'Package deployment is: %r', last_pkg_dep)

            if last_pkg_dep.dep_type == 'deploy':
                dep = last_pkg_dep
                log.log(5, 'Deployment is: %s', dep)

        if dep is None:
            log.log(5, 'Creating new deployment')

            pkg_dep = tagopsdb.deploy.deploy.add_deployment(
                package.id,
                params['user'],
                'deploy'
            )
            dep = pkg_dep
            log.log(5, 'Deployment is: %s', dep)

        self.deploy_to_hosts_or_tiers(
            project, hosts, apptypes, params, dep, app_dep_map, app_host_map
        )

    @staticmethod
    def perform_invalidations(app_dep_map):
        """Perform all invalidations to the requested application tiers"""

        log.debug('Performing invalidations to application tiers')

        for dep_info in app_dep_map.itervalues():
            app_dep, app_type, dep_type, pkg = dep_info
            log.log(5, 'Application deployment is: %r', app_dep)
            log.log(5, 'Application type is: %s', app_type)
            log.log(5, 'Deployment type is: %s', dep_type)
            log.log(5, 'Package is: %r', pkg)

            app_dep.status = 'invalidated'

    @tds.utils.debug
    def perform_redeployments(self, project, hosts, apptypes, params,
                              deployment, app_host_map, app_dep_map):
        """Perform all redeployments to the requested application tiers or
           hosts
        """

        log.debug('Performing redeployments to application tiers or hosts')

        self.deploy_to_hosts_or_tiers(
            project, hosts, apptypes, params, deployment, app_dep_map,
            app_host_map, redeploy=True
        )

    @tds.utils.debug
    def perform_rollbacks(self, project, hosts, apptypes, params, app_pkg_map,
                          app_host_map, app_dep_map):
        """Perform all rollbacks to the requested application tiers
           or hosts
        """

        log.debug('Performing rollbacks to application tiers or hosts')

        # Since a roll back could end up at different versions for
        # each application tier, must do each tier (or host(s) in
        # tier) on its own
        for app_id, pkg_id in app_pkg_map.iteritems():
            app_dep, app_type, dep_type, pkg = app_dep_map[app_id]
            log.log(5, 'Application deployment is: %r', app_dep)
            log.log(5, 'Application type is: %s', app_type)
            log.log(5, 'Deployment type is: %s', dep_type)
            log.log(5, 'Package is: %r', pkg)

            app_id = app_dep.app_id
            log.log(5, 'Application ID is: %s', app_id)

            if app_host_map is None or not app_host_map.get(app_id, None):
                log.log(5, 'Creating new deployment')

                pkg_dep = tagopsdb.deploy.deploy.add_deployment(
                    pkg_id,
                    params['user'],
                    'deploy'
                )
                dep = pkg_dep
                log.log(5, 'Deployment is: %s', dep)
            else:
                # Reset app deployment to 'inprogress' (if tier rollback)
                # or 'incomplete' (if host rollback), will require
                # revalidation
                if hosts:
                    app_dep.status = 'incomplete'
                else:
                    app_dep.status = 'inprogress'

                tagopsdb.Session.commit()

                dep = app_dep.deployment

            if app_host_map is None:
                single_app_host_map = None
            else:
                single_app_host_map = {app_id: app_host_map[app_id]}

            single_app_dep_map = {app_id: app_dep_map[app_id]}

            self.deploy_to_hosts_or_tiers(
                project, hosts, apptypes, params, dep, single_app_dep_map,
                single_app_host_map
            )

    @tds.utils.debug
    def perform_validations(self, project, params, app_dep_map):
        """Perform all validations to the requested application tiers"""

        log.debug('Performing validations to application tiers')

        for dep_info in app_dep_map.itervalues():
            app_dep, app_type, dep_type, pkg = dep_info
            log.log(5, 'Application deployment is: %r', app_dep)
            log.log(5, 'Application type is: %s', app_type)
            log.log(5, 'Deployment type is: %s', dep_type)
            log.log(5, 'Package is: %r', pkg)

            # Commit to DB immediately
            app_dep.status = 'validated'
            tagopsdb.Session.commit()

            log.log(5, 'Committed database (nested) change')
            log.log(5, 'Clearing host deployments for application tier')
            tagopsdb.deploy.deploy.delete_host_deployments(
                project.name,
                app_dep.app_id,
                self.envs[params['env']]
            )

    @tds.utils.debug
    def send_notifications(self, project, hosts, apptypes, params):
        """Send notifications for a given deployment"""

        log.debug('Sending notifications for given deployment')

        deployment = create_deployment(
            project=project,
            hosts=hosts,
            apptypes=apptypes,
            **params
        )

        notification = tds.notifications.Notifications(self.app_config)
        notification.notify(deployment)

    @tds.utils.debug
    def verify_package(self, project, hosts, apptypes, params, hostonly=False):
        """Ensure requested package is valid (exists in the software
           repository)
        """

        log.debug('Verifying requested package')

        pkg = self.get_package(project, params, hostonly)

        app_id_key = lambda x: x.application.id
        if hosts:
            app_host_map = dict(
                (k, list(v))
                for k, v in itertools.groupby(
                    sorted(hosts, key=app_id_key), app_id_key
                )
            )
            return (pkg, app_host_map)
        else:
            return (pkg, apptypes)

    @input_validate('project')
    def add_apptype(self, project, **params):
        """Add a specific application type to the given project"""

        log.debug('Adding application type for project')

        try:
            package_location = tagopsdb.deploy.repo.find_app_location(
                project.name
            )
        except tagopsdb.exceptions.RepoException:
            raise tds.exceptions.TDSException(
                "RepoException when finding package location for project: %s",
                project.name
            )

        try:
            pkg_def = tagopsdb.deploy.package.find_package_definition(
                project.id
            )
        except tagopsdb.exceptions.RepoException:
            raise tds.exceptions.NotFoundError(
                # XXX: who cares?
                "No packages associated with project: %s", project.name
            )

        try:
            tagopsdb.deploy.repo.add_app_packages_mapping(
                project.delegate,
                pkg_def,
                [params['apptype']]
            )
        except tagopsdb.exceptions.RepoException:
            # TODO: Change this to a custome exception
            # Changing this to a custom exception causes failures in feature
            # and unit tests.  test_missing_apptypes in
            # tests/tds/commands/deploy_test throws an error at the last line.
            # It says 'module' has no attribute 'exception' at that line.
            raise Exception(
                "Deploy target does not exist: %s", params['apptype']
            )

        tagopsdb.Session.commit()
        log.debug('Committed database changes')

        return dict(
            result=dict(
                target=params['apptype'],
                project=project.name
            )
        )

    @input_validate('project')
    def delete_apptype(self, project, **params):
        """Delete a specific application type from the given project"""

        log.debug('Removing application type for project')

        app = tagopsdb.deploy.repo.find_app_location(project.name)

        if app is None:
            raise tds.exceptions.NotFoundError(
                'No app found for project "%s"', project.name
            )

        try:
            tagopsdb.deploy.repo.delete_app_packages_mapping(
                app,
                [params['apptype']]
            )
        except tagopsdb.exceptions.RepoException:
            raise tds.exceptions.NotFoundError(
                'Target "%s" does not exist', params['apptype']
            )

        tagopsdb.Session.commit()
        log.debug('Committed database changes')

        return dict(
            result=dict(
                target=params['apptype'],
                project=project.name
            )
        )

    @input_validate('targets')
    @input_validate('project')
    def promote(self, project, hosts=None, apptypes=None, **params):
        """Deploy given version of given project to requested application
           tiers or hosts
        """
        log.debug('Deploying project')

        package, apptypes, app_host_map = self.get_app_info(
            project, hosts, apptypes, params
        )

        if package is None:
            raise tds.exceptions.NotFoundError(
                'Package "%s@%s" does not exist',
                project.name, params['version']
            )

        params['package_name'] = package.name

        app_dep_map = self.find_app_deployments(package, apptypes, params)
        app_host_map, app_dep_map = self.determine_new_deployments(
            project, hosts, apptypes, params, package, app_host_map,
            app_dep_map
        )

        self.send_notifications(project, hosts, apptypes, params)
        self.perform_deployments(
            project, hosts, apptypes, package, params, app_dep_map,
            app_host_map
        )

        tagopsdb.Session.commit()
        log.debug('Committed database changes')
        return dict()

    @input_validate('targets')
    @input_validate('project')
    def invalidate(self, project, hosts=None, apptypes=None, **params):
        """Invalidate a given version of a given project"""

        log.debug('Invalidating for given project')

        # Not a deployment
        params['deployment'] = False

        pkg, apptypes, _app_host_map = self.get_app_info(
            project, hosts, apptypes, params
        )

        if pkg is None:
            raise tds.exceptions.NotFoundError(
                'Package "%s@%s" does not exist',
                project.name, params['version']
            )

        app_dep_map = self.find_app_deployments(pkg, apptypes, params)

        if not len(list(filter(None, app_dep_map.itervalues()))):
            raise tds.exceptions.NotFoundError(
                'No deployments to invalidate for application %r '
                'with version %r in %s environment',
                project.name, params['version'],
                self.envs[params['env']]
            )

        app_dep_map = self.determine_invalidations(project, params, apptypes,
                                                   app_dep_map)
        self.perform_invalidations(app_dep_map)

        tagopsdb.Session.commit()
        log.debug('Committed database changes')
        return dict()

    @input_validate('targets')
    @input_validate('project')
    def show(self, project, apptypes=None, **params):
        """Show deployment information for a given project"""

        log.debug('Showing deployment information for given project')

        version = params.get('version', None)
        pkg_def_app_map = collections.defaultdict(list)

        for target in apptypes:
            for proj_pkg in tagopsdb.ProjectPackage.find(
                project_id=project.id, app_id=target.id
            ):
                pkg_def_app_map[proj_pkg.package_definition].append(target)

        # Find deployments
        deploy_info = []

        for pkg_def in pkg_def_app_map.keys():
            pkg_dep_info = dict(
                environment=params['env'],
                package=pkg_def,
                by_apptype=[],
            )

            for target in pkg_def_app_map[pkg_def]:
                func_args = [
                    pkg_def.name,
                    self.envs[params['env']],
                    target
                ]

                if version is None:
                    curr_app_dep = \
                        tagopsdb.deploy.deploy.find_current_app_deployment(
                            *func_args
                        )
                    prev_app_dep = \
                        tagopsdb.deploy.deploy.find_previous_app_deployment(
                            *func_args
                        )
                else:
                    curr_app_dep = \
                        tagopsdb.deploy.deploy.find_specific_app_deployment(
                            *func_args, version=version
                        )
                    prev_app_dep = None

                host_deps = \
                    tagopsdb.deploy.deploy.find_current_host_deployments(
                        *func_args, version=version
                    )

                pkg_dep_info['by_apptype'].append(dict(
                    apptype=target,
                    current_app_deployment=curr_app_dep,
                    previous_app_deployment=prev_app_dep,
                    host_deployments=host_deps,
                ))

            deploy_info.append(pkg_dep_info)

        return dict(result=deploy_info)

    @input_validate('targets')
    @input_validate('project')
    def rollback(self, project, hosts=None, apptypes=None, **params):
        """Rollback to the previous validated deployed version of given
           project on requested application tiers or hosts
        """

        log.debug('Rolling back project')

        pkg, apptypes, app_host_map = self.get_app_info(
            project, hosts, apptypes, params
        )
        app_dep_map = self.find_app_deployments(pkg, apptypes, params)

        if not len(filter(None, app_dep_map.itervalues())):
            raise tds.exceptions.NotFoundError(
                'Nothing to roll back for application %r in %s '
                'environment', project.name,
                self.envs[params['env']]
            )

        # Save verison of application/deployment map for invalidation
        # at the end of the run
        log.log(5, 'Saving current application/deployment map')
        orig_app_dep_map = app_dep_map

        app_pkg_map, app_host_map, app_dep_map = \
            self.determine_rollbacks(hosts, apptypes, params, app_host_map,
                                     app_dep_map)

        # May need to change when 'package' has name removed (found
        # via 'package_definition')
        params['package_name'] = pkg.name
        params['version'] = pkg.version

        self.send_notifications(project, hosts, apptypes, params)
        self.perform_rollbacks(
            project, hosts, apptypes, params, app_pkg_map, app_host_map,
            app_dep_map
        )

        if not hosts:
            # Now perform invalidations, commit immediately follows
            # Note this is only done for tiers
            self.perform_invalidations(orig_app_dep_map)

        tagopsdb.Session.commit()
        log.debug('Committed database changes')

        return dict()

    @staticmethod
    def get_package_for_target(target, environment):
        """Return the package for the given target in the given environment."""
        deployments = target.app_deployments
        dep = None
        for dep in sorted(deployments, key=lambda x: x.realized, reverse=True):
            if dep.environment != environment.environment:
                continue

            if dep.status in ('inprogress', 'incomplete'):
                raise tds.exceptions.TDSException(
                    'Deploy target "%s" is being deployed to currently',
                    target.name
                )

            if dep.status in ('complete', 'validated'):
                break
        else:
            dep = None

        if dep is not None:
            pkg = dep.deployment.package
            return pkg

        return None

    @input_validate('targets')
    @input_validate('project')
    def restart(self, project, hosts=None, apptypes=None, **params):
        """Restart given project on requested application tiers or hosts"""

        log.debug('Restarting application for project')

        # Not a deployment
        params['deployment'] = False

        environment = tagopsdb.Environment.get(env=params['env'])

        restart_targets = []

        if apptypes:
            for apptype in apptypes:
                pkg = self.get_package_for_target(apptype, environment)
                if pkg is None:
                    continue

                for host in apptype.hosts:
                    if host.environment == environment.environment:
                        restart_targets.append((host, pkg))

        elif hosts:
            for host in hosts:
                pkg = self.get_package_for_target(
                    host.application, environment
                )
                if pkg is None:
                    continue

                restart_targets.append((host, pkg))

        if not restart_targets:
            raise tds.exceptions.NotFoundError(
                'Nothing to restart for project "%s" in %s environment',
                project.name, environment.environment
            )

        restart_targets.sort(key=lambda x: (x[0].name, x[1].name))

        restart_results = {}

        delay = params.get('delay', None)
        for i, (host, pkg) in enumerate(restart_targets):
            # TODO: rework restart_hosts to take a list of hosts/pkgs
            restart_result = self.restart_host(host.name, pkg.name)
            restart_results[(host, pkg)] = restart_result[0]

            if delay is not None and (i+1) < len(restart_targets):
                log.log(5, 'Sleeping for %d seconds...', delay)
                time.sleep(delay)

        return dict(result=restart_results)

    @input_validate('targets')
    @input_validate('project')
    def redeploy(self, project, hosts=None, apptypes=None, **params):
        """Redeploy given project to requested application tiers or hosts"""

        log.debug('Redeploying project')

        pkg, apptypes, app_host_map = self.get_app_info(
            project, hosts, apptypes, params, hostonly=True
        )
        app_dep_map = self.find_app_deployments(pkg, apptypes, params)

        if not len(list(filter(None, app_dep_map.itervalues()))):
            raise tds.exceptions.NotFoundError(
                'Nothing to redeploy for application %r in %s '
                'environment', project.name,
                self.envs[params['env']]
            )

        deployment = tagopsdb.Deployment.find(package_id=pkg.id)[0]
        params['package_name'] = deployment.package.name
        params['version'] = deployment.package.version

        self.send_notifications(project, hosts, apptypes, params)
        self.perform_redeployments(
            project, hosts, apptypes, params, deployment, app_host_map,
            app_dep_map
        )

        tagopsdb.Session.commit()
        log.debug('Committed database changes')

        return dict()

    @input_validate('targets')
    @input_validate('project')
    def validate(self, project, hosts=None, apptypes=None, **params):
        """Validate a given version of a given project"""

        log.debug('Validating for given project')

        # Not a deployment
        params['deployment'] = False

        pkg, apptypes, app_host_map = self.get_app_info(
            project, hosts, apptypes, params
        )

        if pkg is None:
            raise tds.exceptions.NotFoundError(
                'Package "%s@%s" does not exist',
                project.name, params['version']
            )

        app_dep_map = self.find_app_deployments(pkg, apptypes, params)

        if not len(list(filter(None, app_dep_map.itervalues()))):
            raise tds.exceptions.NotFoundError(
                'No deployments to validate for application "%s" '
                'in %s environment', project.name,
                self.envs[params['env']]
            )

        app_dep_map = self.determine_validations(
            project, params, apptypes, app_dep_map
        )
        self.perform_validations(project, params, app_dep_map)

        tagopsdb.Session.commit()
        log.debug('Committed database changes')

        return dict()
