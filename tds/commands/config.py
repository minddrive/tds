'''
Commands to manage config-type projects.
'''

import tagopsdb
import tagopsdb.deploy.repo
import tagopsdb.exceptions

import tds.authorize
import tds.exceptions
import tds.model
import tds.utils
# TODO: this should be a subclass of ApplicationController (or removed)
from .base import validate
from .project import ProjectController
from .deploy import DeployController

import logging

log = logging.getLogger('tds')


class ConfigController(DeployController):
    """Commands to manage deployments for supported config applications"""

    access_levels = DeployController.access_levels.copy()
    access_levels.update(
        create='admin',
        delete='admin',
        repush='environment',
        revert='environment',
        push='environment',
    )

    requires_tier_progression = False

    @validate('project')
    def repush(self, **params):
        'Repush a version of a config project. Same as `deploy redeploy`'
        return super(ConfigController, self).redeploy(**params)

    @validate('project')
    def revert(self, **params):
        '''
        Revert to the previous version of a config project.
        Same as `deploy rollback`
        '''
        return super(ConfigController, self).rollback(**params)

    @validate('project')
    def push(self, **params):
        'Push a new version of a config project. Same as `deploy promote`'
        return super(ConfigController, self).promote(**params)

    @staticmethod
    def verify_package_arch(arch):
        """Ensure architecture for package is supported"""

        table = tagopsdb.model.PackageLocation.__table__
        arches = table.columns['arch'].type.enums

        if arch not in arches:
            raise Exception(
                "Invalid architecture: %s. Should be one of: %s",
                arch,
                u', '.join(sorted(arches))
            )

    def create(self, project, **params):
        # XXX: Replace this with a call
        # XXX: to ApplicationController(log).add(params)
        """Add a new config project to the system"""

        log.debug('Creating new config project')

        project_name = project
        try:
            self.verify_package_arch(params['arch'])
        except Exception as exc:
            return dict(error=exc)

        existing_proj = tds.model.Project.get(name=project_name)

        if existing_proj is not None:
            return dict(error=Exception(
                "Project already exists: %s", existing_proj.name
            ))

        try:
            log.debug('Adding config project to repository')

            # Project type matches project name
            tagopsdb.deploy.repo.add_app_location(
                project_name,
                params['buildtype'],
                params['pkgname'],
                project_name,
                params['pkgpath'],
                params['arch'],
                params['buildhost'],
                params['env_specific']
            )
        except tagopsdb.exceptions.RepoException as exc:
            log.error(exc)
            return dict(error=exc)

        tagopsdb.Session.commit()
        log.debug('Committed database changes')

        return dict(result=tds.model.Project.get(name=project_name))

    @staticmethod
    @validate('project')
    def delete(params):
        """Remove a config project from the system"""
        return ProjectController().delete(**params)
