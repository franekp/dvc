import os
import configobj
from unittest import TestCase
import mock

try:
    from StringIO import StringIO
except ImportError:
    # Python 3
    from io import StringIO

try:
    import __builtin__
    builtin_module_name = '__builtin__'
except ImportError:
    # Python 3
    builtin_module_name = 'builtins'

from dvc.cloud.data_cloud import DataCloud
from dvc.cloud.aws import DataCloudAWS
from dvc.cloud.gcp import DataCloudGCP
from dvc.main import main
from tests.basic_env import TestDvc


class TestConfigTest(TestCase):
    def setUp(self):
        pass

    def _conf(self, s):
        c = configobj.ConfigObj(s)
        return c

    def storage_path_hierarchy_test(self):
        """ StoragePath should be read first from global and then from cloud section """

        c = ("[core]",
             "loglevel =",
             "cloud = aws",
             "storagepath = globalsb/global_storage_path",
             "[aws]",
             "storagepath = awssb/aws_storage_path",
             "credentialpath =",
             "[gcp]",
             "storagepath = googlesb/google_storage_path"
           )
        s = StringIO('\n'.join(c))
        conf = self._conf(s)
        cloud = DataCloud(None, conf)
        self.assertIsInstance(cloud._cloud, DataCloudAWS)
        self.assertEqual(cloud._cloud.storage_bucket, 'globalsb')
        self.assertEqual(cloud._cloud.storage_prefix, 'global_storage_path')

        c = ("[core]",
             "loglevel =",
             "cloud = Aws",
             "[aws]",
             "storagepath = awssb/aws_storage_path",
             "credentialpath =",
             "[gcp]",
             "storagepath = googlesb/google_storage_path"
           )
        s = StringIO('\n'.join(c))
        conf = self._conf(s)
        cloud = DataCloud(None, conf)
        self.assertIsInstance(cloud._cloud, DataCloudAWS)
        self.assertEqual(cloud._cloud.storage_bucket, 'awssb')
        self.assertEqual(cloud._cloud.storage_prefix, 'aws_storage_path')

    def mocked_open_aws_default_credentials(klass, file, asdf):
        """ mocked open for ~/.aws/credentials """
        if file == os.path.expanduser('~/.aws/credentials'):
            creds0 = ("[default]",
                      "aws_access_key_id = default_access_id",
                      "aws_secret_access_key = default_sekret")
            return StringIO('\n'.join(creds0))

        creds1 = ("[default]",
                  "aws_access_key_id = override_access_id",
                  "aws_secret_access_key = override_sekret")

        return StringIO('\n'.join(creds1))

    def aws_credentials_default_tes_t_DISABLED(self):
        """ in absence of [AWS] -> CredentialPath, aws creds should be read from ~/.aws/credentials """

        default_path = os.path.expanduser('~/.aws/credentials')
        c = ("[core]",
             "loglevel =",
             "cloud = aws",
             "[aws]",
             "storagepath = awssb/aws_storage_path",
             "credentialpath =",
           )
        s = StringIO('\n'.join(c))

        patcher = mock.patch(builtin_module_name + '.open', side_effect=self.mocked_open_aws_default_credentials)

        # patcher.start()
        conf = self._conf(s)
        cloud = DataCloud(None, conf)
        aws_creds = cloud._cloud._get_credentials()
        patcher.stop()

        self.assertEqual(aws_creds[0], 'default_access_id')
        self.assertEqual(aws_creds[1], 'default_sekret')

    def mocked_isfile(file):
        """ tell os some_credential_path exists """
        return file == 'some_credential_path'

    @mock.patch('dvc.config.os.path.isfile', side_effect = mocked_isfile)
    def aws_credentials_specified_tes_t_DISABLED(self, isfile_function):
        """ in presence of [AWS] -> CredentialPath, use those credentials """

        c = ("[core]",
             "loglevel =",
             "cloud = aws",
             "[aws]",
             "storagePath = awssb/aws_storage_path",
             "credentialpath = some_credential_path",
           )
        s = StringIO('\n'.join(c))

        patcher = mock.patch(builtin_module_name + '.open', side_effect=self.mocked_open_aws_default_credentials)

        patcher.start()
        conf = self._conf(s)
        cloud = DataCloud(None, conf)
        aws_creds = cloud._cloud._get_credentials()
        patcher.stop()

        self.assertEqual(aws_creds[0], 'override_access_id')
        self.assertEqual(aws_creds[1], 'override_sekret')


class TestConfigCLI(TestDvc):
    def _contains(self, section, field, value):
        config = configobj.ConfigObj(self.dvc.config.config_file)
        if section not in config.keys():
            return False

        if field not in config[section].keys():
            return False

        if config[section][field] != value:
            return False

        return True

    def test(self):
        section = 'setsection'
        field = 'setfield'
        section_field = '{}.{}'.format(section, field)
        value = 'setvalue'
        newvalue = 'setnewvalue'

        ret = main(['config', section_field, value])
        self.assertEqual(ret, 0)
        self.assertTrue(self._contains(section, field, value))

        ret = main(['config', section_field])
        self.assertEqual(ret, 0)

        ret = main(['config', section_field, newvalue])
        self.assertEqual(ret, 0)
        self.assertTrue(self._contains(section, field, newvalue))
        self.assertFalse(self._contains(section, field, value))

        ret = main(['config', section_field, '--unset'])
        self.assertEqual(ret, 0)
        self.assertFalse(self._contains(section, field, value))

    def test_non_existing(self):
        #FIXME check stdout/err

        ret = main(['config', 'non_existing_section.field'])
        self.assertEqual(ret, 1)

        ret = main(['config', 'global.non_existing_field'])
        self.assertEqual(ret, 1)

        ret = main(['config', 'non_existing_section.field', '-u'])
        self.assertEqual(ret, 1)

        ret = main(['config', 'global.non_existing_field', '-u'])
        self.assertEqual(ret, 1)
