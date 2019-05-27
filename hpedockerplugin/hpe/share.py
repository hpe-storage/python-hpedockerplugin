DEFAULT_MOUNT_SHARE = "True"
MAX_SHARES_PER_FPG = 16


def create_metadata(backend, cpg, fpg, share_name, size,
                    readonly=False, nfs_options=None, comment='',
                    fsMode=None, fsOwner=None):
    return {
        'id': None,
        'backend': backend,
        'cpg': cpg,
        'fpg': fpg,
        'vfs': None,
        'name': share_name,
        'size': size,
        'readonly': readonly,
        'nfsOptions': nfs_options,
        'protocol': 'nfs',
        'clientIPs': [],
        'comment': comment,
        'fsMode': fsMode,
        'fsOwner': fsOwner,
    }
