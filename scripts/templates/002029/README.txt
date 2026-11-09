Dataset Title: Morphoelectric Diversity and Specialization of Neuronal Cell Types in the Primate Striatum.
This is a dataset funded through the BICAN program. More information at https://www.portal.brain-bican.org/

ACKNOWLEDGEMENTS

Citation:
Liu, X.-P., Dalley, R., Johansen, N., Budzillo, A., Walling-Bell, S., Zeng, H., Sorensen, S. A., Lee, B. R., Ting, J., Lein, E. S., & Kalmbach, B. (2026). Morphoelectric Diversity and Specialization of Neuronal Cell Types in the Primate Striatum [Data set]. DANDI Archive. https://dandiarchive.org/dandiset/002029

Funding:
NIMH UM1MH130981


DESCRIPTION

This dataset contains single cell patch-clamp electrophysiological recordings from non-human primate (Macaca) striatum cell types, acquired via the Patch-seq method. These data are included in the publication 'Morphoelectric Diversity and Specialization of Neuronal Cell Types in the Primate Striatum' by Liu et al. (2026), Cell: https://doi.org/10.1016/j.cell.2026.10.028


LICENSE

Attribution 4.0 International (CC BY 4.0) https://creativecommons.org/licenses/by/4.0/


ASSOCIATED DATASETS

Data Collection: Morphoelectric Diversity and Specialization of Neuronal Cell Types in the Primate Striatum.
Repository: NeMO Archive
URL: https://assets.nemoarchive.org/dat-nsm6mxv

Data Collection: Morphoelectric Diversity and Specialization of Neuronal Cell Types in the Primate Striatum.
Repository: Brain Image Library (BIL)
URL: https://doi.org/10.35077/g.1210


USAGE NOTES

This Patch-seq dataset consists of patch-clamp electrophysiological recording sessions released as NWB files at DANDI. Associated transcriptomic data are released at the NeMO Archive, and associated morphology data at the Brain Image Library (see ASSOCIATED DATASETS above).

This dataset is organized following the BIDS Specification v1.10.0 (see https://bids.neuroimaging.io/ for more information) as a BIDS 'study' dataset. The dataset includes NWB files with data from the recording session for each cell in the 'sourcedata/raw' folder, as well as the following accessory files that contain additional metadata and links:

* participants.tsv:  A table of metadata associated with the Donors/subjects (species, sex and age).

* participants.json:  Descriptions for each column in the participants.tsv table.

* mapping.tsv:  A table of metadata for each cell that was recorded. Each cell in the dataset has one recording session, found here as a single file in NWB format. The mapping table contains the local name of the Dissociated Cell Sample for each cell, the brain structure in which the cell was located, Allen Institute LIMS identifiers associated with the cell, and links to the NWB file both in this dataset and in the source Dandiset it was originally uploaded to.

* mapping.json:  Descriptions for each column in the mapping.tsv table.

* datasets.tsv:  A table with links to the source Dandisets that these NWB files originated from, associated with the original data upload. Note that the source Dandisets contain recordings from additional cells that were not included in this publication.

* datasets.json:  Descriptions for each column in the datasets.tsv table.


The metadata tables may be updated as additional or updated metadata becomes available. Please refer to the latest version of this dataset at DANDI for the most up-to-date tables.
