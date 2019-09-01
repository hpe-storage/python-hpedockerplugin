from oslo_log import log as logging
import os

LOG = logging.getLogger(__name__)

class ScsiUtils():

    def rescan_scsi_host(self, device_name):
        path = '/sys/class/scsi_host/'
        for file in os.listdir(path):
            print('File %s' % file)
            if os.path.isdir(path + file) and 'host' in file:
                path_to_scan = path + file + '/scan'
                print('Scanning %s' % path_to_scan)
                LOG.info('Scanning %s' % path_to_scan)
                os.system('echo "- - -" > '+path_to_scan)
        # delete the faulty disk
        LOG.info(' Device to delete .. %s ' % device_name)
        os.system("echo 1 > /sys/block/"+device_name.split('/')[2]+"/device/delete")


