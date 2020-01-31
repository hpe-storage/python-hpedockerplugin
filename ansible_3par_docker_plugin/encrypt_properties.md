# Encrypting the ansible inventory properties file before installing the docker volume plugin

Currently, the properties file is a plain text YAML wherein the settings and properties exist which would then be used to create the hpe.conf file on each Kubernetes/Openshift node.

Though the array passwords could be encrypted in respective hpe.conf using py-3parencryptor utility, the property file would still contain the credentials in plain text.

To solve this problem, ansible vault is used. This vault has the capability to encrypt the complete file. In this case, the properties file could be encrypted and password could be set on it. Once encrypted, the contents cannot be viewed without obtaining the password to decrypt the content.

How to create the properties file:
```
ansible-vault create ansible_3par_docker_plugin/properties/plugin_configuration_properties.yml
```
This will prompt to set the password and will encrypt the file. The contents can be written to the file and saved. It will no longer be possible to view the contents of the file through an editor


How to edit the properties file:
```
ansible-vault edit ansible_3par_docker_plugin/properties/plugin_configuration_properties.yml
```

The contents of the properties file including the array credentials are now encrypted and safe.

How to execute the playbook with the vault-ed properties file
The playbooks can be run by adding ```--ask-vault-pass``` in the playbook execution command
```
ansible-playbook -i hosts install_script.yml --ask-vault-pass
```
