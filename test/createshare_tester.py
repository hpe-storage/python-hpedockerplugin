import time

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
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_share_etcd = self.mock_objects['mock_share_etcd']
        mock_share_etcd.get_share.side_effect = [
            # 1. Skip check for share existence <-- REST LAYER
            exception.EtcdMetadataNotFound(msg="Key not found"),
            # 2. Skip check for share existence <-- File Mgr
            exception.EtcdMetadataNotFound(msg="Key not found"),
            # 17. Allow quota_id to be updated in share
            data.create_share_args,
        ]

        mock_fp_etcd = self.mock_objects['mock_fp_etcd']
        mock_fp_etcd.get_backend_metadata.side_effect = [
            # 3. Get current default FPG. No backend metadata exists
            # This will result in EtcdDefaultFpgNotPresent exception
            # which will execute _create_default_fpg flow which tries
            # to generate default FPG/VFS names using backend metadata
            exception.EtcdMetadataNotFound(msg="Key not found"),
            # 4. _create_default_fpg flow tries to generate default FPG/VFS
            # names using backend metadata. For first share, no backend
            # metadata exists which results in EtcdMetadataNotFound. As a
            # result, backend metadata is CREATED:
            # {
            #   'ips_in_use': [],
            #   'ips_locked_for_use': [],
            #   'counter': 0
            # }
            # DockerFpg_0 and DockerVFS_0 names are returned for creation.
            exception.EtcdMetadataNotFound(msg="Key not found"),
            # 11. Claim available IP
            data.etcd_bkend_mdata_with_default_fpg,
            # 12. Allow marking of IP to be in use
            data.etcd_bkend_mdata_with_default_fpg,
            # 16. Allow marking of IP to be in use
            data.etcd_bkend_mdata_with_default_fpg,
        ]

        mock_file_client = self.mock_objects['mock_file_client']
        mock_file_client.http.post.side_effect = [
            # 5. Create FPG DockerFpg_0 at the backend. This results in 3PAR
            # task creation with taskId present in fpg_create_response. Wait
            # for task completion in step #6 below
            (data.fpg_create_resp, data.fpg_create_body),
            # 8. Create VFS
            (data.vfs_create_resp, data.vfs_create_body),
            # 13. Create share response and body
            (data.sh_create_resp, data.sh_create_body),
            # 14. Set quota
            (data.set_quota_resp, data.set_quota_body)
        ]

        mock_file_client.getTask.side_effect = [
            # 6. Wait for task completion and add default_fpg to backend
            # metadata as below:
            # {
            #   'default_fpgs': {cpg_name: ['Docker_Fpg0']},
            #   'ips_in_use': [],
            #   'ips_locked_for_use': [],
            #   'counter': 0
            # }
            # Save FPG metadata as well
            data.fpg_create_task_body,
            # 9. Wait for VFS create task completion
            data.vfs_create_task_body,
        ]
        mock_file_client.TASK_DONE = 1

        mock_file_client.http.get.side_effect = [
            # 7. Get all VFS to check IPs in use
            (data.all_vfs_resp, data.all_vfs_body),
            # 15. Verify VFS is in good state
            (data.get_vfs_resp, data.get_vfs_body)
        ]

        # 10. Allow IP info to be updated by returning empty dict
        # This brings VFS creation process to completion
        mock_fp_etcd.get_fpg_metadata.return_value = {}

    def check_response(self, resp):
        import pdb
        pdb.set_trace()
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


# TestCreateShareDefaultNoDefFpg
class TestCreateDefaultShare(CreateShareUnitTest):
    def get_request_params(self):
        return {u"Name": u"MyDefShare_01",
                u"Opts": {u"filePersona": u''}}

    def setup_mock_objects(self):
        mock_share_etcd = self.mock_objects['mock_share_etcd']
        mock_share_etcd.get_share.side_effect = [
            # Skip check for share existence <-- REST LAYER
            exception.EtcdMetadataNotFound("Key not found"),
            # Skip check for share existence <-- File Mgr
            exception.EtcdMetadataNotFound("Key not found")
        ]
        mock_fp_etcd = self.mock_objects['mock_fp_etcd']
        mock_fp_etcd.get_backend_metadata.side_effect = [
            # While trying to get default FPG
            exception.EtcdMetadataNotFound,
            # FPG/VFS name generation
            exception.EtcdMetadataNotFound,
            # Claim available IP
            data.etcd_bkend_mdata_with_default_fpg,
        ]

        # This covers the fpg-vfs names generator almost 100%
        # mock_fp_etcd.get_backend_metadata.side_effect = [
        #     data.bkend_mdata_with_default_fpg,
        #     data.bkend_mdata_with_default_fpg,
        # ]

        mock_file_client = self.mock_objects['mock_file_client']
        mock_file_client.http.get.side_effect = [
            data.bkend_fpg,
            data.bkend_vfs,
            data.quotas_for_fpg,
        ]
        mock_file_client.http.post.side_effect = [
            (data.fpg_create_resp, data.fpg_create_body),
            (data.sh_create_resp, data.sh_create_body),
            (data.set_quota_resp, data.set_quota_body)
        ]
        mock_file_client.getTask.return_value = (
            data.fpg_create_task_resp, data.fpg_create_task_body
        )

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.createVolume.assert_called()
