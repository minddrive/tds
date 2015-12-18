"""
REST API view for tier deployments.
"""

from cornice.resource import resource, view

import tds.model
import tagopsdb.model
from .base import BaseView, init_view

@resource(collection_path="/tier_deployments", path="/tier_deployments/{id}")
@init_view(name="tier-deployment", model=tds.model.AppDeployment)
class TierDeploymentView(BaseView):

    param_routes = {
        'tier_id': 'app_id',
    }

    defaults = {
        'status': 'pending',
    }

    required_post_fields = ('deployment_id', 'tier_id', 'environment_id',
                            'package_id')

    unique_together = (
        ('deployment_id', 'tier_id', 'package_id'),
    )

    individual_allowed_methods = dict(
        GET=dict(description="Get tier deployment matching ID."),
        PUT=dict(description="Update tier deployment matching ID."),
        DELETE=dict(description="Delete tier deployment matching ID."),
    )

    collection_allowed_methods = dict(
        GET=dict(description="Get a list of tier deployments, optionally by "
                 "limit and/or start."),
        POST=dict(description="Add a new tier deployment."),
    )

    def validate_tier_deployment_delete(self):
        if self.name not in self.request.validated:
            return
        if self.request.validated[self.name].deployment.status != 'pending':
            self.request.errors.add(
                'path', 'id',
                'Cannot delete tier deployment whose deployment is no longer '
                'pending.'
            )
            self.request.errors.status = 403

    def validate_individual_tier_deployment(self, request):
        self.get_obj_by_name_or_id(obj_type='Tier deployment',
                                   model=self.model, param_name='id',
                                   can_be_name=False, dict_name=self.name)

    def validate_conflicting_env(self, request_type):
        """
        Validate that the user isn't attempting to add or update a tier
        deployment s.t. the associated or attempted to be associated deployment
        has another host or tier deployment in a different environment from
        that of this tier deployment.
        """
        if request_type == 'POST':
            if 'environment_id' not in self.request.validated_params or \
                    'deployment_id' not in self.request.validated_params:
                return
            own_environment = tagopsdb.model.Environment.get(
                id=self.request.validated_params['environment_id']
            )
            deployment = tds.model.Deployment.get(
                id=self.request.validated_params['deployment_id']
            )
            name = 'environment_id'
        elif 'environment_id' not in self.request.validated_params and \
                'deployment_id' not in self.request.validated_params:
            return
        elif self.name not in self.request.validated:
            return
        elif 'environment_id' not in self.request.validated_params:
            own_environment = self.request.validated[self.name].environment_obj
            deployment = tds.model.Deployment.get(
                id=self.request.validated_params['deployment_id']
            )
            name = 'deployment_id'
        elif 'deployment_id' not in self.request.validated_params:
            own_environment = tagopsdb.model.Environment.get(
                id=self.request.validated_params['environment_id']
            )
            deployment = self.request.validated[self.name].deployment
            name = 'environment_id'
        else:
            own_environment = tagopsdb.model.Environment.get(
                id=self.request.validated_params['environment_id']
            )
            deployment = tds.model.Deployment.get(
                id=self.request.validated_params['deployment_id']
            )
            name = 'environment_id'
        if None in (own_environment, deployment):
            return
        for app_dep in deployment.app_deployments:
            if self.name in self.request.validated and app_dep.id == \
                    self.request.validated[self.name].id:
                continue
            if app_dep.environment_id != own_environment.id:
                self.request.errors.add(
                    'query', name,
                    'Cannot deploy to different environments with same '
                    'deployment. There is a tier deployment associated with '
                    'this deployment with ID {app_id} and environment {env}.'
                    .format(app_id=app_dep.id, env=app_dep.environment)
                )
                self.request.errors.status = 409
        for host_dep in deployment.host_deployments:
            # Ignore host deployments for this tier deployment since they will
            # be changed anyway if the put request is otherwise valid.
            if self.name in self.request.validated and \
                    host_dep.host.app_id == \
                    self.request.validated[self.name].app_id:
                continue
            if host_dep.host.environment_id != own_environment.id:
                self.request.errors.add(
                    'query', name,
                    'Cannot deploy to different environments with same '
                    'deployment. There is a host deployment associated with '
                    'this deployment with ID {tier_id} and environment {env}.'
                    .format(tier_id=host_dep.id, env=host_dep.host.environment)
                )
                self.request.errors.status = 409

    def validate_tier_deployment_put(self):
        if self.name not in self.request.validated:
            return
        if self.request.validated[self.name].deployment.status != 'pending':
            self.request.errors.add(
                'path', 'id',
                'Users cannot modify tier deployments whose deployments are no'
                ' longer pending.'
            )
            self.request.errors.status = 403
            return
        if 'status' in self.request.validated_params:
            self.request.errors.add(
                'query', 'status',
                "Users cannot change the status of tier deployments."
            )
            self.request.errors.status = 403
        self.validate_conflicting_env('PUT')
        self._validate_foreign_key('tier_id', 'tier', tds.model.AppTarget)
        self._validate_foreign_key('environment_id', 'environment',
                                   tagopsdb.model.Environment)
        self._validate_foreign_key('package_id', 'package', tds.model.Package)
        self._validate_unique_together("PUT", "tier deployment")
        # If the package_id is being changed and the deployment isn't pending:
        if 'package_id' in self.request.validated_params and \
                self.request.validated_params['package_id'] != \
                self.request.validated[self.name].package_id and \
                self.request.validated[self.name].deployment.status != \
                'pending':
            self.request.errors.add(
                'query', 'package_id',
                'Cannot change package_id for a tier deployment with a '
                'non-pending deployment.'
            )
            self.request.errors.status = 403
        if not any(
            x in self.request.validated_params for x in ('tier_id',
                                                         'package_id')
        ):
            return
        pkg_id = self.request.validated_params['package_id'] if 'package_id' \
            in self.request.validated_params else \
            self.request.validated[self.name].package_id
        tier_id = self.request.validated_params['tier_id'] if 'tier_id' in \
            self.request.validated_params else \
            self.request.validated[self.name].app_id
        self._validate_project_package(pkg_id, tier_id)

    def _validate_project_package(self, pkg_id, tier_id):
        found_pkg = tds.model.Package.get(id=pkg_id)
        found_tier = tds.model.AppTarget.get(id=tier_id)
        if not (found_pkg and found_tier):
            return
        found_project_pkg = tagopsdb.model.ProjectPackage.find(
            pkg_def_id=found_pkg.pkg_def_id,
            app_id=tier_id,
        )
        if not found_project_pkg:
            self.request.errors.add(
                'query', 'tier_id' if 'tier_id' in self.request.validated_params
                else 'package_id',
                'Tier {t_name} is not associated with the application {a_name}'
                ' for any projects.'.format(
                    t_name=found_tier.name,
                    a_name=found_pkg.application.name,
                )
            )
            self.request.errors.status = 403

    def validate_tier_deployment_post(self):
        if 'status' in self.request.validated_params:
            if self.request.validated_params['status'] != 'pending':
                self.request.errors.add(
                    'query', 'status',
                    'Status must be pending for new tier deployments.'
                )
                self.request.errors.status = 403
        self.validate_conflicting_env('POST')
        self._validate_foreign_key('tier_id', 'tier', tds.model.AppTarget)
        self._validate_foreign_key('environment_id', 'environment',
                                   tagopsdb.model.Environment)
        self._validate_foreign_key('package_id', 'package', tds.model.Package)
        self._validate_unique_together("POST", "tier deployment")
        if not all(
            x in self.request.validated_params for x in ('package_id',
                                                         'tier_id')
        ):
            return
        self._validate_project_package(
            self.request.validated_params['package_id'],
            self.request.validated_params['tier_id'],
        )

    @view(validators=('validate_put_post', 'validate_post_required',
                      'validate_obj_post', 'validate_cookie'))
    def collection_post(self):
        for host in tds.model.HostTarget.find(
            app_id=self.request.validated_params['tier_id'],
            environment_id=self.request.validated_params['environment_id']
        ):
            host_dep = tds.model.HostDeployment.create(
                host_id=host.id,
                deployment_id=self.request.validated_params['deployment_id'],
                user=self.request.validated['user'],
                status='pending',
                package_id=self.request.validated_params['package_id'],
            )
        self.request.validated_params['user'] = self.request.validated['user']
        return self._handle_collection_post()

    @view(validators=('validate_individual', 'validate_put_post',
                      'validate_obj_put', 'validate_cookie'))
    def put(self):
        curr_dep = self.request.validated[self.name]
        if 'tier_id' in self.request.validated_params:
            new_tier_id = self.request.validated_params['tier_id']
            tier_id_different = new_tier_id != curr_dep.app_id
        else:
            new_tier_id = curr_dep.app_id
            tier_id_different = False

        if 'environment_id' in self.request.validated_params:
            new_env_id = self.request.validated_params['environment_id']
            env_id_different = new_env_id != curr_dep.environment_id
        else:
            new_env_id = curr_dep.environment_id
            env_id_different = False

        if 'package_id' in self.request.validated_params:
            new_package_id = self.request.validated_params['package_id']
            package_id_different = new_package_id != curr_dep.package_id
        else:
            new_package_id = curr_dep.package_id
            package_id_different = False

        if 'deployment_id' in self.request.validated_params:
            new_dep_id = self.request.validated_params['deployment_id']
        else:
            new_dep_id = curr_dep.deployment_id
        # If environment, tier or package ID is being changed, delete all
        # host deployments associated with this tier deployment and create new
        # ones based on the new state of this tier deployment.
        if env_id_different or tier_id_different or package_id_different:
            for host_dep in curr_dep.deployment.host_deployments:
                if host_dep.host.app_id == curr_dep.app_id:
                    tagopsdb.Session.delete(host_dep)
            for host in tds.model.HostTarget.find(
                app_id=new_tier_id,
                environment_id=new_env_id,
            ):
                host_dep = tds.model.HostDeployment.create(
                    host_id=host.id,
                    deployment_id=new_dep_id,
                    user=self.request.validated['user'],
                    status='pending',
                    package_id=new_package_id
                )
        for attr in self.request.validated_params:
            setattr(
                curr_dep,
                self.param_routes[attr] if attr in self.param_routes else attr,
                self.request.validated_params[attr],
            )
        tagopsdb.Session.commit()
        return self.make_response(
            self.to_json_obj(self.request.validated[self.name])
        )