import time

from hpe3parclient import exceptions as hpe3par_ex

import hpedockerplugin.exception as exception
import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpedockerunittest


class CreateShareUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'volumedriver_create'

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

    def override_configuration(self, all_configs):
        pass

    # TODO: check_response and setup_mock_objects can be implemented
    # here for the normal happy path TCs here as they are same


class TestCreateFirstDefaultShare(CreateShareUnitTest):
    def get_request_params(self):
        return {u"Name": u"MyDefShare_01",
                u"Opts": {u"filePersona": u''}}

    def setup_mock_objects(self):
        # ***** BEGIN - Required mock objects *****
        mock_etcd = self.mock_objects['mock_etcd']
        mock_share_etcd = self.mock_objects['mock_share_etcd']
        mock_fp_etcd = self.mock_objects['mock_fp_etcd']
        mock_file_client = self.mock_objects['mock_file_client']
        # ***** END - Required mock objects *****

        # ***** BEGIN - Setup side effect lists *****
        etcd_get_share_side_effect = list()
        mock_share_etcd.get_share.side_effect = etcd_get_share_side_effect

        etcd_get_backend_metadata_side_effect = list()
        mock_fp_etcd.get_backend_metadata.side_effect = \
            etcd_get_backend_metadata_side_effect

        etcd_get_fpg_metadata_side_effect = list()
        mock_fp_etcd.get_fpg_metadata.side_effect = \
            etcd_get_fpg_metadata_side_effect

        file_client_http_post_side_effect = list()
        mock_file_client.http.post.side_effect = \
            file_client_http_post_side_effect

        file_client_get_task_side_effect = list()
        mock_file_client.getTask.side_effect = \
            file_client_get_task_side_effect

        file_client_http_get_side_effect = list()
        mock_file_client.http.get.side_effect = \
            file_client_http_get_side_effect
        # ***** END - Setup side effect lists *****

        # Step #1:
        # Skip check for volume existence <-- REST layer

        # Step #0:
        # Skip check for volume existence <-- REST LAYER
        mock_etcd.get_vol_byname.return_value = None

        # Step #1:
        # Skip check for share existence <-- REST LAYER
        etcd_get_share_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #2:
        # Skip check for share existence <-- File Mgr
        etcd_get_share_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #3:
        # Get current default FPG. No backend metadata exists
        # This will result in EtcdDefaultFpgNotPresent exception
        # which will execute _create_default_fpg flow which tries
        # to generate default FPG/VFS names using backend metadata
        etcd_get_backend_metadata_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #4:
        # _create_default_fpg flow tries to generate default FPG/VFS
        # names using backend metadata. For first share, no backend
        # metadata exists which results in EtcdMetadataNotFound. As a
        # result, backend metadata is CREATED:
        # {
        #   'ips_in_use': [],
        #   'ips_locked_for_use': [],
        #   'counter': 0
        # }
        # DockerFpg_0 and DockerVFS_0 names are returned for creation.
        etcd_get_backend_metadata_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #5:
        # Create FPG DockerFpg_0 at the backend. This results in 3PAR
        # task creation with taskId present in fpg_create_response. Wait
        # for task completion in step #6 below
        file_client_http_post_side_effect.append(
            (data.fpg_create_resp, data.fpg_create_body)
        )
        # Step #6:
        # Wait for task completion and add default_fpg to backend
        # metadata as below:
        # {
        #   'default_fpgs': {cpg_name: ['Docker_Fpg0']},
        #   'ips_in_use': [],
        #   'ips_locked_for_use': [],
        #   'counter': 0
        # }
        # Save FPG metadata as well
        file_client_get_task_side_effect.append(
            data.fpg_create_task_body
        )
        # Step #7:
        # Claim available IP
        etcd_get_backend_metadata_side_effect.append(
            data.etcd_bkend_mdata_with_default_fpg
        )
        # Step #8:
        # Get all VFS to check IPs in use
        file_client_http_get_side_effect.append(
            (data.all_vfs_resp, data.all_vfs_body)
        )
        # Step #9:
        # Create VFS
        file_client_http_post_side_effect.append(
            (data.vfs_create_resp, data.vfs_create_body)
        )
        # Step #10:
        # Wait for VFS create task completion
        file_client_get_task_side_effect.append(
            data.vfs_create_task_body
        )
        mock_file_client.TASK_DONE = 1

        # Step #11:
        # Allow IP info to be updated by returning empty dict
        # This brings VFS creation process to completion
        etcd_get_fpg_metadata_side_effect.append({})

        # Step #12:
        # Allow marking of IP to be in use
        etcd_get_backend_metadata_side_effect.append(
            data.etcd_bkend_mdata_with_default_fpg
        )
        # Step #13:
        # Create share response and body
        file_client_http_post_side_effect.append(
            (data.sh_create_resp, data.sh_create_body)
        )
        # Step #14:
        # Set quota
        file_client_http_post_side_effect.append(
            (data.set_quota_resp, data.set_quota_body)
        )
        # Step #15:
        # Verify VFS is in good state
        file_client_http_get_side_effect.append(
            (data.get_vfs_resp, data.get_vfs_body)
        )
        # Step #16:
        # Allow marking of IP to be in use
        etcd_get_backend_metadata_side_effect.append(
            data.etcd_bkend_mdata_with_default_fpg
        )
        # Step #17:
        # Allow quota_id to be updated in share
        etcd_get_share_side_effect.append(
            data.create_share_args
        )

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})
        for i in range(1, 3):
            status = data.create_share_args.get('status')
            if status == 'AVAILABLE' or status == 'FAILED':
                print("Share is in %s state!" % status)
                break
            else:
                print("Share is in %s state. Checking in few seconds "
                      "again..." % status)
                time.sleep(2)


class TestCreateSecondDefaultShare(CreateShareUnitTest):
    def get_request_params(self):
        return {u"Name": u"MyDefShare_01",
                u"Opts": {u"filePersona": u''}}

    def setup_mock_objects(self):

        # ***** BEGIN - Required mock objects *****
        mock_etcd = self.mock_objects['mock_etcd']
        mock_share_etcd = self.mock_objects['mock_share_etcd']
        mock_fp_etcd = self.mock_objects['mock_fp_etcd']
        mock_file_client = self.mock_objects['mock_file_client']
        # ***** END - Required mock objects *****

        # ***** BEGIN - Setup side effect lists *****
        etcd_get_share_side_effect = list()
        mock_share_etcd.get_share.side_effect = etcd_get_share_side_effect

        etcd_get_backend_metadata_side_effect = list()
        mock_fp_etcd.get_backend_metadata.side_effect = \
            etcd_get_backend_metadata_side_effect

        file_client_http_post_side_effect = list()
        mock_file_client.http.post.side_effect = \
            file_client_http_post_side_effect

        file_client_get_task_side_effect = list()
        mock_file_client.getTask.side_effect = \
            file_client_get_task_side_effect

        file_client_http_get_side_effect = list()
        mock_file_client.http.get.side_effect = \
            file_client_http_get_side_effect
        # ***** END - Setup side effect lists *****

        # Step #1:
        # Skip check for volume existence <-- REST layer
        mock_etcd.get_vol_byname.return_value = None

        # Step #2:
        # Skip check for share existence <-- REST LAYER
        etcd_get_share_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #3: Skip check for share existence <-- File Mgr
        etcd_get_share_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #4:
        # Get current default FPG. Backend metadata exists. FPG info
        # needs to be prepared in the below format and returned. For
        # this, step #5, #6 and #7 needs to be executed:
        # fpg_info = {
        #     'ips': {netmask: [ip]},
        #     'fpg': fpg_name,
        #     'vfs': vfs_name,
        # }
        etcd_get_backend_metadata_side_effect.append(
            data.etcd_bkend_mdata_with_default_fpg
        )
        # Step #5:
        # Get FPG from the backend so that its total capacity can
        # be ascertained and checked against sum of sizes of shares
        # existing on this FPG to find out if a new share with the
        # specified/default size can be accommodated on this FPG
        file_client_http_get_side_effect.append(
            (data.resp, data.bkend_fpg)
        )
        # Step #6:
        # Get all quotas set for the file-stores under the current FPG
        file_client_http_get_side_effect.append(
            (data.resp, data.get_quotas_for_fpg)
        )
        # Step #7:
        # Get VFS corresponding the the FPG so that IP and netmask can be
        # set within the FPG info being returned
        file_client_http_get_side_effect.append(
            (data.get_vfs_resp, data.get_vfs_body)
        )
        # Step #8:
        # Create share response and body
        file_client_http_post_side_effect.append(
            (data.sh_create_resp, data.sh_create_body)
        )
        # Step #9:
        # Set quota
        file_client_http_post_side_effect.append(
            (data.set_quota_resp, data.set_quota_body)
        )
        # Step #10:
        # Allow quota_id to be updated in share
        etcd_get_share_side_effect.append(
            data.create_share_args,
        )

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})
        for i in range(1, 3):
            status = data.create_share_args.get('status')
            if status == 'AVAILABLE' or status == 'FAILED':
                print("Share is in %s state!" % status)
                break
            else:
                print("Share is in %s state. Checking in few seconds "
                      "again..." % status)
                time.sleep(2)


class TestCreateShareOnNewFpg(CreateShareUnitTest):
    def get_request_params(self):
        return {u"Name": u"MyDefShare_01",
                u"Opts": {u"filePersona": u"",
                          u"fpg": u"NewFpg"}}

    def setup_mock_objects(self):

        # ***** BEGIN - Required mock objects *****
        mock_etcd = self.mock_objects['mock_etcd']
        mock_share_etcd = self.mock_objects['mock_share_etcd']
        mock_fp_etcd = self.mock_objects['mock_fp_etcd']
        mock_file_client = self.mock_objects['mock_file_client']
        # ***** END - Required mock objects *****

        # ***** BEGIN - Setup side effect lists *****
        etcd_get_share_side_effect = list()
        mock_share_etcd.get_share.side_effect = etcd_get_share_side_effect

        etcd_get_backend_metadata_side_effect = list()
        mock_fp_etcd.get_backend_metadata.side_effect = \
            etcd_get_backend_metadata_side_effect

        etcd_get_fpg_metadata_side_effect = list()
        mock_fp_etcd.get_fpg_metadata.side_effect = \
            etcd_get_fpg_metadata_side_effect

        file_client_http_post_side_effect = list()
        mock_file_client.http.post.side_effect = \
            file_client_http_post_side_effect

        file_client_get_task_side_effect = list()
        mock_file_client.getTask.side_effect = \
            file_client_get_task_side_effect

        file_client_http_get_side_effect = list()
        mock_file_client.http.get.side_effect = \
            file_client_http_get_side_effect
        # ***** END - Setup side effect lists *****

        # Step #1:
        # Skip check for volume existence <-- REST layer
        mock_etcd.get_vol_byname.return_value = None

        # Step #2:
        # Skip check for share existence <-- REST LAYER
        etcd_get_share_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #3:
        # Skip check for share existence <-- File Mgr
        etcd_get_share_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )

        # Step #4:
        # No FPG metadata for specified FPG name present in ETCD
        etcd_get_fpg_metadata_side_effect.append(
            exception.EtcdMetadataNotFound
        )

        # Step #5:
        # Get FPG from backend
        file_client_http_get_side_effect.append(
            (data.no_fpg_resp, data.no_fpg_body)
        )

        # Step #6:
        # Get all quotas for the specified FPG
        file_client_http_get_side_effect.append(
            (data.resp, data.get_quotas_for_fpg)
        )

        # Step #7:
        # Get VFS for the specified FPG so that IP information can
        # be added to the share metadata
        file_client_http_get_side_effect.append(
            (data.get_vfs_resp, data.get_vfs_body)
        )

        # Step #8:
        # Create share response and body
        file_client_http_post_side_effect.append(
            (data.sh_create_resp, data.sh_create_body)
        )
        # Step #9:
        # Set quota
        file_client_http_post_side_effect.append(
            (data.set_quota_resp, data.set_quota_body)
        )
        # Step #10:
        # Allow quota_id to be updated in share
        etcd_get_share_side_effect.append(
            data.create_share_args,
        )

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()


class TestCreateShareOnLegacyFpg(CreateShareUnitTest):
    def get_request_params(self):
        return {u"Name": u"MyDefShare_01",
                u"Opts": {u"filePersona": u"",
                          u"fpg": u"LegacyFpg"}}

    def setup_mock_objects(self):

        # ***** BEGIN - Required mock objects *****
        mock_etcd = self.mock_objects['mock_etcd']
        mock_share_etcd = self.mock_objects['mock_share_etcd']
        mock_fp_etcd = self.mock_objects['mock_fp_etcd']
        mock_file_client = self.mock_objects['mock_file_client']
        # ***** END - Required mock objects *****

        # ***** BEGIN - Setup side effect lists *****
        etcd_get_share_side_effect = list()
        mock_share_etcd.get_share.side_effect = etcd_get_share_side_effect

        etcd_get_backend_metadata_side_effect = list()
        mock_fp_etcd.get_backend_metadata.side_effect = \
            etcd_get_backend_metadata_side_effect

        etcd_get_fpg_metadata_side_effect = list()
        mock_fp_etcd.get_fpg_metadata.side_effect = \
            etcd_get_fpg_metadata_side_effect

        file_client_http_post_side_effect = list()
        mock_file_client.http.post.side_effect = \
            file_client_http_post_side_effect

        file_client_get_task_side_effect = list()
        mock_file_client.getTask.side_effect = \
            file_client_get_task_side_effect

        file_client_http_get_side_effect = list()
        mock_file_client.http.get.side_effect = \
            file_client_http_get_side_effect
        # ***** END - Setup side effect lists *****

        # Step #1:
        # Skip check for volume existence <-- REST layer
        mock_etcd.get_vol_byname.return_value = None

        # Step #2:
        # Skip check for share existence <-- REST LAYER
        etcd_get_share_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #3:
        # Skip check for share existence <-- File Mgr
        etcd_get_share_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )

        # Step #4:
        # No FPG metadata for specified FPG name present in ETCD
        etcd_get_fpg_metadata_side_effect.append(
            exception.EtcdMetadataNotFound
        )

        # Step #5:
        # Return legacy FPG from backend
        file_client_http_get_side_effect.append(
            (data.resp, data.bkend_fpg)
        )

        # Step #6:
        # Get all quotas for the specified FPG
        file_client_http_get_side_effect.append(
            (data.resp, data.get_quotas_for_fpg)
        )

        # Step #7:
        # Get VFS for the specified FPG so that IP information can
        # be added to the share metadata
        file_client_http_get_side_effect.append(
            (data.get_vfs_resp, data.get_vfs_body)
        )

        # Step #8:
        # Create share response and body
        file_client_http_post_side_effect.append(
            (data.sh_create_resp, data.sh_create_body)
        )
        # Step #9:
        # Set quota
        file_client_http_post_side_effect.append(
            (data.set_quota_resp, data.set_quota_body)
        )
        # Step #10:
        # Allow quota_id to be updated in share
        etcd_get_share_side_effect.append(
            data.create_share_args,
        )

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()


class TestCreateFirstDefaultShareSetQuotaFails(CreateShareUnitTest):
    def get_request_params(self):
        return {u"Name": u"MyDefShare_01",
                u"Opts": {u"filePersona": u''}}

    def setup_mock_objects(self):
        # ***** BEGIN - Required mock objects *****
        mock_etcd = self.mock_objects['mock_etcd']
        mock_share_etcd = self.mock_objects['mock_share_etcd']
        mock_fp_etcd = self.mock_objects['mock_fp_etcd']
        mock_file_client = self.mock_objects['mock_file_client']
        # ***** END - Required mock objects *****

        # ***** BEGIN - Setup side effect lists *****
        etcd_get_share_side_effect = list()
        mock_share_etcd.get_share.side_effect = etcd_get_share_side_effect

        etcd_get_backend_metadata_side_effect = list()
        mock_fp_etcd.get_backend_metadata.side_effect = \
            etcd_get_backend_metadata_side_effect

        etcd_get_fpg_metadata_side_effect = list()
        mock_fp_etcd.get_fpg_metadata.side_effect = \
            etcd_get_fpg_metadata_side_effect

        file_client_http_post_side_effect = list()
        mock_file_client.http.post.side_effect = \
            file_client_http_post_side_effect

        file_client_get_task_side_effect = list()
        mock_file_client.getTask.side_effect = \
            file_client_get_task_side_effect

        file_client_http_get_side_effect = list()
        mock_file_client.http.get.side_effect = \
            file_client_http_get_side_effect
        # ***** END - Setup side effect lists *****

        # Step #0:
        # Skip check for volume existence <-- REST LAYER
        mock_etcd.get_vol_byname.return_value = None

        # Step #1:
        # Skip check for share existence <-- REST LAYER
        etcd_get_share_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #2:
        # Skip check for share existence <-- File Mgr
        etcd_get_share_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #3:
        # Get current default FPG. No backend metadata exists
        # This will result in EtcdDefaultFpgNotPresent exception
        # which will execute _create_default_fpg flow which tries
        # to generate default FPG/VFS names using backend metadata
        etcd_get_backend_metadata_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #4:
        # _create_default_fpg flow tries to generate default FPG/VFS
        # names using backend metadata. For first share, no backend
        # metadata exists which results in EtcdMetadataNotFound. As a
        # result, backend metadata is CREATED:
        # {
        #   'ips_in_use': [],
        #   'ips_locked_for_use': [],
        #   'counter': 0
        # }
        # DockerFpg_0 and DockerVFS_0 names are returned for creation.
        etcd_get_backend_metadata_side_effect.append(
            exception.EtcdMetadataNotFound(msg="Key not found")
        )
        # Step #5:
        # Create FPG DockerFpg_0 at the backend. This results in 3PAR
        # task creation with taskId present in fpg_create_response. Wait
        # for task completion in step #6 below
        file_client_http_post_side_effect.append(
            (data.fpg_create_resp, data.fpg_create_body)
        )
        # Step #6:
        # Wait for task completion and add default_fpg to backend
        # metadata as below:
        # {
        #   'default_fpgs': {cpg_name: ['Docker_Fpg0']},
        #   'ips_in_use': [],
        #   'ips_locked_for_use': [],
        #   'counter': 0
        # }
        # Save FPG metadata as well
        file_client_get_task_side_effect.append(
            data.fpg_create_task_body
        )
        # Step #7:
        # Claim available IP
        etcd_get_backend_metadata_side_effect.append(
            data.etcd_bkend_mdata_with_default_fpg
        )
        # Step #8:
        # Get all VFS to check IPs in use
        file_client_http_get_side_effect.append(
            (data.all_vfs_resp, data.all_vfs_body)
        )
        # Step #9:
        # Create VFS
        file_client_http_post_side_effect.append(
            (data.vfs_create_resp, data.vfs_create_body)
        )
        # Step #10:
        # Wait for VFS create task completion
        file_client_get_task_side_effect.append(
            data.vfs_create_task_body
        )
        mock_file_client.TASK_DONE = 1

        # Step #11:
        # Verify VFS is in good state
        file_client_http_get_side_effect.append(
            (data.get_vfs_resp, data.get_vfs_body)
        )

        # Step #12:
        # Allow IP info to be updated by returning empty dict
        # This brings VFS creation process to completion
        etcd_get_fpg_metadata_side_effect.append({})

        # Step #13:
        # Allow marking of IP to be in use
        etcd_get_backend_metadata_side_effect.append(
            data.etcd_bkend_mdata_with_default_fpg
        )
        # Step #14:
        # Allow marking of IP to be in use
        etcd_get_backend_metadata_side_effect.append(
            data.etcd_bkend_mdata_with_default_fpg
        )
        # Step #15:
        # Create share response and body
        file_client_http_post_side_effect.append(
            (data.sh_create_resp, data.sh_create_body)
        )
        # Step #16:
        # Set quota FAILS
        file_client_http_post_side_effect.append(
            hpe3par_ex.HTTPBadRequest("Set Quota Failed")
        )
        # Step #17:
        # Delete file store requires its ID. Query file store
        # by name
        file_client_http_get_side_effect.append(
            (data.get_fstore_resp, data.get_fstore_body)
        )
        # Step #18:
        # IP marked for use to be returned to IP pool as part of rollback
        # Return backend metadata that has the IPs in use
        etcd_get_backend_metadata_side_effect.append(
            data.etcd_bkend_mdata_with_default_fpg_and_ips
        )
        # Step #19:
        # To delete backend FPG, get FPG by name to retrieve its ID
        file_client_http_get_side_effect.append(
            (data.get_bkend_fpg_resp, data.bkend_fpg)
        )
        # Step #20:
        # Wait for delete FPG task completion
        mock_file_client.http.delete.return_value = \
            (data.fpg_delete_task_resp, data.fpg_delete_task_body)
        file_client_get_task_side_effect.append(
            data.fpg_delete_task_body
        )
        mock_file_client.TASK_DONE = 1

        # Step #21:
        # Allow removal of default FPG from backend metadata
        etcd_get_backend_metadata_side_effect.append(
            data.etcd_bkend_mdata_with_default_fpg_and_ips
        )

    def check_response(self, resp):
        pass
