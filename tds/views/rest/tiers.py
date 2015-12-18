"""
REST API view for app tiers.
"""

from cornice.resource import resource, view

import tds.model
import tagopsdb

from . import utils
from .base import BaseView, init_view

@resource(collection_path="/tiers", path="/tiers/{name_or_id}")
@init_view(name='tier', model=tds.model.AppTarget)
class TierView(BaseView):
    """
    Tier view. This object maps to the /tiers and /tiers/{name_or_id} URLs.
    An object of this class is initalized to handle each request.
    The collection_* methods correspond to the /tiers URL while the
    others correspond to the /tiers/{name_or_id} URL.
    """

    # URL parameter routes to Python object fields.
    # Params not included are mapped to themselves.
    param_routes = {
        'name': 'app_type',
        'ganglia_name': 'ganglia_group_name',
    }

    defaults = {}

    required_post_fields = ("name",)

    permissions = {
        'put': 'admin',
        'delete': 'admin',
        'collection_post': 'admin',
    }

    individual_allowed_methods = dict(
        GET=dict(description="Get tier matching name or ID."),
        PUT=dict(description="Update tier matching name or ID."),
    )

    collection_allowed_methods = dict(
        GET=dict(description="Get a list of tiers, optionally by limit and/"
                 "or start."),
        POST=dict(description="Add a new tier."),
    )

    def validate_tier_post(self):
        """
        Validate a POST request by preventing collisions over unique fields and
        validating that a Ganglia object exists for the given ID.
        """
        self._validate_name("POST")
        self._validate_foreign_key('ganglia_id', 'Ganglia object',
                                   tagopsdb.model.Ganglia, 'cluster_name')

    def validate_tier_put(self):
        """
        Validate a PUT request by preventing collisions over unique fields and
        validating that a Ganglia object exists for the given ID.
        """
        self._validate_name("PUT")
        self._validate_foreign_key('ganglia_id', 'Ganglia object',
                                   tagopsdb.model.Ganglia, 'cluster_name')