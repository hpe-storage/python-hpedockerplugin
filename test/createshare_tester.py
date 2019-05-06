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


class TestCreateShareDefault(CreateShareUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.createVolume.assert_called()

    def get_request_params(self):
        return {u"Name": u"MyDefShare_01",
                u"Opts": {u"filePersona": u'',
                          u"backend": u"DEFAULT",
                          # u"fpg": u"imran_fpg",
                          # u"nfsOpts": u"hard,proto=tcp,nfsvers=4,intr",
                          u"readonly": u"False"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None
