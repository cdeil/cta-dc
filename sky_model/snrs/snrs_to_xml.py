"""
Convert SNRs to XML format.
"""
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.table import Table, Column

SOURCE_LIBRARY_TEMPLATE = """\
<?xml version="1.0" standalone="no"?>

<source_library title="CTA 1DC simulated supernova remnants">

{xml_sources}

</source_library>
"""

SOURCE_TEMPLATE = """
 <source name="{source_name}" type="ExtendedSource">
{xml_spectral}
{xml_spatial}
 </source>
"""

SPATIAL_TEMPLATE = """\
    <spatialModel type="RadialShell">
    <parameter name="GLON" value="{glon:.5f}" scale="1.0" min="-360" max="360" free="1"/>
    <parameter name="GLAT" value="{glat:.5f}" scale="1.0" min="-90" max="90" free="1"/>
    <parameter name="Radius" value="{radius:.5f}" scale="1.0" min="1e-10" max="1000"  free="1"/>
    <parameter name="Width" value="{width:.5f}" scale="1.0" min="1e-10" max="1000"  free="1"/>
    </spatialModel>"""

SPECTRUM_TEMPLATE = """\
    <spectrum type="NodeFunction">
    {xml_spectrum_nodes}\
    </spectrum>"""

# Multi-line, more readable version
SPECTRUM_NODE_TEMPLATE_READABLE = """\
    <node>
    <parameter name="Energy" value="{energy:.5f}" scale="1e06" min="0.1"   max="1.0e20" free="0"/>
    <parameter name="Intensity" value="{dnde:.5g}" scale="1e-10" min="1e-20" max="1000.0" free="1"/>
    </node>
"""

# Here you can select which one you want
SPECTRUM_NODE_TEMPLATE = SPECTRUM_NODE_TEMPLATE_READABLE


def make_table_spectrum_xml(sed_energy, sed_dnde):
    xml_spectrum_nodes = ''
    for energy, dnde in zip(sed_energy, sed_dnde):
        xml_spectrum_nodes += SPECTRUM_NODE_TEMPLATE.format(
            energy=1e-6 * energy,
            dnde=1e+10 * dnde,
        )

    return SPECTRUM_TEMPLATE.format(xml_spectrum_nodes=xml_spectrum_nodes)


def make_spectral_point_selection(row):
    # Jürgen requested that we remove nodes with zero or very low flux
    # so that it works for ctools.
    # So here we remove the ones below an arbirtrary low threshold

    # In addition we noticed that some SNRs have all fluxes very low
    # We remove these super faint SNRs completely.

    mask = row['sed_dnde'] > 1e-20
    sed_energy = row['sed_energy'][mask]
    sed_dnde = row['sed_dnde'][mask]

    keep = (mask.sum() > 3)

    return dict(
        sed_energy=sed_energy,
        sed_dnde=sed_dnde,
        keep=keep,
    )


def make_snr_xml(table_sed, table):
    print('Number of SNRs from Pierre: {}'.format(len(table)))
    print('Number of SNRs from Pierre: {}'.format(len(table_sed)))
    snr_in_output = 0

    keep = []
    xml_sources = ''
    for row in table_sed:

        spec = make_spectral_point_selection(row)
        keep.append(spec['keep'])

        if not spec['keep']:
            continue

        snr_in_output += 1
        xml_spectral = make_table_spectrum_xml(
            sed_energy=spec['sed_energy'],
            sed_dnde=spec['sed_dnde'],
        )

        # Assumption on width of the SNR shell
        # Pierre simulates a thin shell
        # but Jurgen cannot handle 0, we put 5% of the shell radius

        width_fraction = 0.05
        radius = u.Quantity(row['sigma'], 'arcmin').to('deg')
        width = width_fraction * radius

        xml_spatial = SPATIAL_TEMPLATE.format(
            glon=row['glon'],
            glat=row['glat'],
            radius=radius.value,
            width=width.value,
        )

        source_name = 'snr_{}'.format(row.index)
        xml_source = SOURCE_TEMPLATE.format(
            source_name=source_name,
            xml_spectral=xml_spectral,
            xml_spatial=xml_spatial,
        )

        xml_sources += xml_source

    table['keep'] = Column(keep, description='')
    print('Number of SNRs in output XML: {}'.format(snr_in_output))
    xml = SOURCE_LIBRARY_TEMPLATE.format(xml_sources=xml_sources)
    return xml


def add_sed_columns(table):
    energy_array = np.array(table.meta['energy_array'])
    sed_energy = np.tile(energy_array, reps=(len(table), 1))

    table.info()

    # Copy over fluxes into array column
    sed_dnde = np.empty_like(sed_energy)
    for col_idx in range(50):
        sed_dnde[:, col_idx] = table.columns[6 + col_idx]

    table['sed_energy'] = u.Quantity(sed_energy, 'TeV').to('MeV')
    table['sed_dnde'] = u.Quantity(sed_dnde, 'cm-2 s-1 TeV-1').to('cm-2 s-1 MeV-1')


if __name__ == '__main__':
    for version in [1, 2]:
        filename = 'ctadc_skymodel_gps_sources_snr_{}.ecsv'.format(version)
        print('Reading {}'.format(filename))
        table = Table.read(filename, format='ascii.ecsv')
        #table.remove_column('skip')
        table_sed = Table.read(filename, format='ascii.ecsv')
        add_sed_columns(table_sed)

        print(table)

        xml = make_snr_xml(table_sed, table)
        print(table)


        filename = 'ctadc_skymodel_gps_sources_snr_{}_keep.ecsv'.format(version)
        print('Writing {}'.format(filename))
        table.write(filename, format='ascii.ecsv', overwrite=True)

        filename = 'ctadc_skymodel_gps_sources_snr_{}.xml'.format(version)
        print('Writing {}'.format(filename))
        Path(filename).write_text(xml)
