"""
TODO:
- check for consistency against XML observation lists
- check if AGN observations are wobble observations

"""
import logging
from pathlib import Path
import tempfile
import hashlib
import subprocess
from astropy.table import Table
import xmltodict

BASE_PATH = Path('1dc/1dc')

log = logging.getLogger()

# {'@name': 'AGN', '@id': '510000', '@instrument': 'CTA',
#  'parameter': [OrderedDict([('@name', 'Pointing'), ('@ra', '35.665'), ('@dec', '43.0355')]),
#                OrderedDict([('@name', 'EnergyBoundaries'), ('@emin', '30000'), ('@emax', '50000000')]),
#                OrderedDict([('@name', 'GoodTimeIntervals'), ('@tmin', '662774400'), ('@tmax', '662776200')]),
#                OrderedDict([('@name', 'TimeReference'), ('@mjdrefi', '51544'), ('@mjdreff', '0.5'), ('@timeunit', 's'),
#                             ('@timesys', 'TT'), ('@timeref', 'LOCAL')]),
#                OrderedDict([('@name', 'RegionOfInterest'), ('@ra', '35.665'), ('@dec', '43.0355'), ('@rad', '5')]),
#                OrderedDict([('@name', 'Deadtime'), ('@deadc', '0.98')]),
#                OrderedDict([('@name', 'Calibration'), ('@database', '1dc'), ('@response', 'North_z20_50h')]),
#                OrderedDict([('@name', 'EventList'), ('@file', '$CTADATA/data/baselin


# From https://forge.in2p3.fr/projects/data-challenge-1-dc-1/wiki#Observation-pattern
docs_obs_infos = dict(
    gps=dict(n_obs=3270),
    gc=dict(n_obs=1671),
    egal=dict(n_obs=1271),
    agn=dict(n_obs=1920),
)


class IndexFileChecker:
    def __init__(self, dataset):
        self.dataset = dataset

    def run(self):
        self.check_against_docs()
        self.check_against_xml()
        # self.print_ref()

    def check_against_docs(self):
        obs_table = self.obs_table
        n_obs_actual = len(obs_table)
        n_obs_expected = docs_obs_infos[self.dataset]['n_obs']
        if n_obs_actual != n_obs_expected:
            log.error(f'dataset={self.dataset!r}, n_obs_actual={n_obs_actual}, n_obs_expected={n_obs_expected}')

    def check_against_xml(self):
        xml_list = self.xml_list
        # print(dict(xml_data[0]))
        obs_table = self.obs_table
        assert len(xml_list) == len(obs_table)

        for xml_data, obs_data in zip(xml_list, obs_table):
            self.check_observation(xml_data, obs_data)

    @staticmethod
    def check_observation(xml_data, obs_data):
        assert int(xml_data['@id']) == int(obs_data['OBS_ID'])
        # print(xml_data['parameter'][6])
        # print(obs_data['IRF'])
        assert xml_data['parameter'][6]['@response'] == obs_data['IRF']

    @property
    def xml_list(self):
        filename = BASE_PATH / f'obs/obs_{self.dataset}_baseline.xml'
        log.debug(f'Reading {filename}')
        data = xmltodict.parse(filename.read_text())
        return data['observation_list']['observation']

    @property
    def obs_table(self):
        filename = BASE_PATH / 'index' / self.dataset / 'obs-index.fits.gz'
        log.debug(f'Reading {filename}')
        return Table.read(str(filename))

        # def print_ref(self):
        #     obs_table = self.obs_table
        #     lines = obs_table.pformat()
        #     path = Path('checks/refs/'
        #     print(s)


def check_index_files():
    datasets = ['agn', 'egal', 'gc', 'gps']
    # datasets = ['agn']
    for dataset in datasets:
        IndexFileChecker(dataset).run()


def check_composite_index_files():
    n_obs = 8132

    filename = BASE_PATH / 'index/all/obs-index.fits.gz'
    log.debug(f'Reading {filename}')
    table = Table.read(filename)
    assert len(table) == n_obs

    filename = BASE_PATH / 'index/all/hdu-index.fits.gz'
    log.debug(f'Reading {filename}')
    table = Table.read(filename)
    assert len(table) == 6 * n_obs


def check_index_files_checksums(dirname):
    log.info(f'Checking checksums for folder: {dirname}')
    for filename, md5_expected in [
        # dict(zip(['filename', 'md5'], _.split())) for _ in
        _.split() for _ in
        Path('checks/refs/checksums.txt').read_text().splitlines()
    ]:
        path = Path(dirname) / filename
        md5_actual = hashlib.md5(path.read_bytes()).hexdigest()
        if md5_actual == md5_expected:
            log.debug(f'Checksum OK: {filename} {md5_expected}')
        else:
            log.error(f'Checksum mismatch: {filename} expected={md5_expected} actual={md5_actual}')


def check_checksums():
    """Check that local files and tarball and checksums under version control are consistent."""
    check_index_files_checksums('1dc')

    with tempfile.TemporaryDirectory() as tmpdirname:
        cmd = f'tar zxf 1dc/index.tar.gz -C {tmpdirname}'
        subprocess.call(cmd, shell=True)
        check_index_files_checksums(tmpdirname)


if __name__ == '__main__':
    logging.basicConfig(level='INFO')
    check_index_files()
    check_composite_index_files()
    check_checksums()
