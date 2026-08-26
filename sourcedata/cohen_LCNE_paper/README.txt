
Dataset Title: Patch-seq profiling of mouse locus coeruleus norepinephrine neurons.
This is a dataset funded through the BICAN program. More information at https://www.portal.brain-bican.org/

ACKNOWLEDGEMENTS

Citation:
Su, Z., Kosillo, P., Jung, K., Chen, S., Summers, M. T., Piet, A., Hou, H., Hagihara, K. M., Friedmann, D., Ho-Shing, O., Becker, M. I., Chartrand, T., Grotz, P., Hilton-VanOsdall, E., Lee, M., Javeri, R., Tuggle, S. L., Ouellette, N., Myers, H., Laiton, C., Wulf, K., Rohde, J., Buccino, A., Arshadi, C., Wang, D., Seshamani, S., Vasquez, S., Eng, C. M., Ollerenshaw, D. R., Dee, N., Casper, T., Ho, W., Jungert, M., Jordan, A., Phillips, E., Chakka, A. B., Nasirova, K., Blake, K., McCutcheon, A., Koch, M., Vergara, M. C., Smith, K. A., Jarsky, T., Lusk, N., Rue, M., Chen, X., Siegle, J. H., Glaser, A. K., Lee, B. R., Svoboda, K., Isogai, Y., Chandrashekar, J. V., & Cohen, J. Y. (2026). Patch-seq profiling of mouse locus coeruleus norepinephrine neurons [Data set]. DANDI Archive.

Funding:
NIMH R01MH134833 Structure-function cell atlas for norepinephrine and serotonin neurons. 
https://reporter.nih.gov/project-details/11250142


DESCRIPTION

This dataset contains electrophysiological recordings for the Patch-seq analysis of Mus musculus locus coeruleus norepinephrine neurons using SMART-seq V4 sequencing of locus coeruleus (LC) norepinephrine neurons. These data are included in the publication 'Topographic structure and function of locus coeruleus norepinephrine neurons' by Su et al (2026).


LICENSE

Attribution 4.0 International (CC BY 4.0) https://creativecommons.org/licenses/by/4.0/


PROTOCOLS

Patch-Seq Recording and Extraction V.3: https://www.protocols.io/view/patch-seq-recording-and-extraction-8epv51n45l1b/v3


ASSOCIATED DATASETS

Data Collection: Patch-seq profiling of mouse locus coeruleus norephinephrine neurons (Raw).

Repository: NeMO Data Archive
Data Files are Accessible from URL: https://assets.nemoarchive.org/collection/nemo:col-s96tk9a

Species: mouse
Modality: Transcriptomics
Technique: SMARTSeqSC
Status: complete
Access: open
License: CC BY 4.0
Description: Patch-seq analysis of Mus musculus locus coeruleus norephinephrine neurons using SMART-seq SC sequencing of locus coeruleus (LC) norephinephrine neurons.


USAGE NOTES

This Patch-seq dataset consists of patch-clamp electrophysiological recording sessions released as NWB files at DANDI. A subset of these cells also have associated transcriptomic data released as FASTQ files at the NeMO Data Archive (see ASSOCIATED DATASETS above for information and download instructions). Specimen provenance and additional metadata for the related biosamples can also be found at NIMP Analytics (https://brain-specimenportal.org/nimp_analytics/) using the BICAN NHash identifiers for these subjects and cell samples (see below for more information).

This dataset is organized following the BIDS Specification v1.10.0 (see https://bids.neuroimaging.io/ for more information). The dataset includes NWB files with data from the recording session for each cell in the 'sourcedata' folder, as well the following accessory files that contain additional metadata and links:

* participants.tsv:  A table of metadata associated with the Donors/subjects. This includes the Donor NHash identifier (a unique BICAN-wide identifier for the Donor/subject), and a direct link to NIMP Analytics for each Donor where additional Donor related metadata may be accessed.

* participants.json:  Descriptions for each column in the participants.tsv table.

* mapping.tsv:  A table of metadata for each cell that was recorded. Each cell in the dataset has one recording session, found here as a single file in NWB format. The mapping table contains the 'Dissociated Cell Sample' NHash identifier for each cell, which is the BICAN unique identifier assigned to each recorded cell. The table also includes the related 'Library Aliquot' NHash identifier that is assigned to the library aliquot that was sequenced from the recorded cell, and direct links to the NeMO Archive to access metadata and download the associated FASTQ files for the cell. Note that not all cells in this dataset have transcriptomic data available. The mapping table also includes anatomical location metadata and direct links to NIMP Analytics for each cell to access additional biosample metadata and view specimen provenance.

* mapping.json:  Descriptions for each column in the mapping.tsv table.

* datasets.tsv:  A table with links to the source Dandisets that these NWB files originated from, associated with the original data upload. Note that the source Dandisets contain recordings from additional cells that were not included in this publication.

* datasets.json:  Descriptions for each column in the datasets.tsv table.


The metadata tables may be updated as additional or updated metadata becomes available. Please refer to the latest version of this dataset at DANDI for the most up-to-date tables.

