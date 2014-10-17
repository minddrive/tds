"""Commands to manage the deployment repository."""

import logging

import tagopsdb
import tagopsdb.exceptions
import tagopsdb.deploy.package
import tagopsdb.deploy.repo

import tds.exceptions
import tds.authorize
import tds.model
import tds.utils

from .base import BaseController, validate
from .project import ProjectController

log = logging.getLogger('tds')


class RepositoryController(BaseController):
    """Commands to manage the deployment repository."""
    access_levels = dict(
        list='environment',
        add='admin',
        delete='admin',
    )

    @validate('project')
    def list(self, **params):
        """Repository list subcommand."""
        return ProjectController(self.app_config).list(**params)

    @validate('project')
    def delete(self, project, **params):
        """Repository delete subcommand."""
        # Note: this will go away when project/app are separated
        pkg_def_ids = set([x.pkg_def_id for x in
                          tagopsdb.ProjectPackage.find(project_id=project.id)])

        proj = ProjectController(self.app_config).delete(
            project=project, **params
        )

        # Note: package_locations table will be removed for 2.0
        pkg_loc = tagopsdb.PackageLocation.get(
            app_name=proj['result'].name
        )

        if pkg_loc is not None:
            pkg_loc.delete()

        # Note: this will go away when project/app are separated
        for pkg_def_id in pkg_def_ids:
            tagopsdb.PackageDefinition.get(id=pkg_def_id).delete()

        tagopsdb.Session.commit()
        return proj

    @staticmethod
    def verify_package_arch(arch):
        """Ensure architecture for package is supported."""

        table = tagopsdb.model.PackageLocation.__table__
        arches = table.columns['arch'].type.enums

        if arch not in arches:
            raise tds.exceptions.InvalidInputError(
                "Invalid architecture: %s. Should be one of: %s",
                arch,
                u', '.join(sorted(arches))
            )

    def add(self, **params):
        """Add a given project to the repository."""

        log.debug('Adding application %r to repository',
                  params['project'])

        self.verify_package_arch(params['arch'])

        targets = []
        for apptype in params['apptypes']:
            target = tds.model.AppTarget.get(name=apptype)
            if target is None:
                raise tds.exceptions.NotFoundError(
                    "Apptype '%s' does not exist", apptype
                )

            targets.append(target)

        try:
            # For now, project_type is 'application'
            params['projecttype'] = 'application'
            project, project_new, pkg_def = \
                tagopsdb.deploy.repo.add_app_location(
                    params['projecttype'],
                    params['buildtype'],
                    params['pkgname'],
                    params['project'],
                    params['pkgpath'],
                    params['arch'],
                    params['buildhost'],
                )
            log.log(5, 'Application\'s Location ID is: %d',
                    project.id)

            log.debug('Mapping Location ID to various applications')
            tagopsdb.deploy.repo.add_app_packages_mapping(
                project_new,
                pkg_def,
                params['apptypes']
            )
        except tagopsdb.exceptions.RepoException as e:
            log.error(e)
            return

        if params.get('config', None):
            # XXX: this should go away as config is not special
            log.debug('Adding application %r to config project %r',
                      params['project'], params['config'])

            try:
                # Transitional code for refactoring
                config_new = tagopsdb.deploy.repo.find_project(
                    params['config']
                )
                config_def = tagopsdb.deploy.package.find_package_definition(
                    config_new.id
                )

                log.log(
                    5, 'Config project %r\'s project: %r',
                    params['config'], config_new
                )
                tagopsdb.deploy.repo.add_app_packages_mapping(
                    config_new,
                    config_def,
                    params['apptypes']
                )
            except tagopsdb.exceptions.RepoException as e:
                log.error(e)
                return

        tagopsdb.Session.commit()
        log.debug('Committed database changes')

        return dict(result=tds.model.Project.get(name=params['project']))
