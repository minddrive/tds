"""
REST view for most recent deployment of an application to a tier in a given
environment.
"""

from cornice.resource import resource, view

import tds.model
import tagopsdb.model
from .base import BaseView, init_view
from . import types, descriptions
from .urls import ALL_URLS
from .permissions import CURRENT_TIER_DEPLOYMENT_PERMISSIONS


@resource(path=ALL_URLS['current_tier_deployment'])
@init_view(name="current-tier-deployment", model=tds.model.AppDeployment,
           set_params=False)
class CurrentTierDeployment(BaseView):
    """
    REST view for most recent deployment of an application to a tier in a given
    environment.
    """

    param_routes = {
        'tier_id': 'app_id',
    }

    defaults = {}

    individual_allowed_methods = dict(
        GET=dict(description="Get the most recent completed tier deployment "
                 "for an application, tier, and environment."),
    )

    full_types = types.TIER_DEPLOYMENT_TYPES

    full_descriptions = descriptions.TIER_DEPLOYMENT_DESCRIPTIONS

    permissions = CURRENT_TIER_DEPLOYMENT_PERMISSIONS

    def validate_individual_current_tier_deployment(self, request):
        """
        Validate that the application and tier being selected exist and that
        there is a deployment of the application on the tier.
        If one exists, assign the tier deployment to
        request.validated[self.name].
        Add an error otherwise.
        """
        self.get_obj_by_name_or_id('application', tds.model.Application,
                                   'pkg_name')
        self.get_obj_by_name_or_id('tier', tds.model.AppTarget, 'app_type',
                                   param_name='tier_name_or_id')
        self.get_obj_by_name_or_id('environment', tagopsdb.model.Environment,
                                   name_attr='environment',
                                   param_name='environment_name_or_id')
        if not all(x in request.validated for x in ('application', 'tier',
                                                    'environment')):
            return

        found_assoc = self.session.query(
            tagopsdb.model.ProjectPackage
        ).filter_by(
            pkg_def_id=request.validated['application'].id,
            app_id=request.validated['tier'].id,
        )

        if not found_assoc:
            request.errors.add(
                'path', 'tier_name_or_id',
                'Association of tier {t_name} with the application {a_name} '
                'does not exist for any projects.'.format(
                    t_name=request.validated['tier'].name,
                    a_name=request.validated['application'].name,
                )
            )
            request.errors.status = 403
            return

        self._validate_params(['must_be_validated', 'select'])
        self._validate_json_params({
            'must_be_validated': 'boolean',
            'select': 'string',
        })
        validated = 'must_be_validated' in request.validated_params and \
            request.validated_params['must_be_validated']

        request.validated[self.name] = request.validated['application'] \
            .get_latest_completed_tier_deployment(
                request.validated['tier'].id,
                request.validated['environment'].id,
                must_be_validated=validated,
            )
        if not request.validated[self.name]:
            request.errors.add(
                'path', 'environment_name_or_id',
                'Validated{addendum} deployment of application {a_name} on '
                'tier {t_name} in {e_name} environment does not exist.'.format(
                    addendum='' if validated else ' or complete',
                    a_name=request.validated['application'].name,
                    t_name=request.validated['tier'].name,
                    e_name=request.validated['environment'].environment,
                )
            )
            request.errors.status = 404

    @view(validators=('method_not_allowed',))
    def put(self):
        """
        Method not allowed.
        """
        return self.make_response({})

    @view(validators=('method_not_allowed',))
    def delete(self):
        """
        Method not allowed.
        """
        return self.make_response({})
