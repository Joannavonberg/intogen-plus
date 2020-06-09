import os

from pyliftover import LiftOver

from intogen_core.readers import TSVReader

HEADER = [
        "Hugo_Symbol", "Chromosome", "Start_Position", "End_Position",
        "Strand", "Variant_Classification", "Variant_Type", "Reference_Allele",
        "Tumor_Seq_Allele1", "Tumor_Seq_Allele2", "Tumor_Sample_Barcode",
    ]

LIFTOVER = LiftOver('hg38', to_db='hg19', search_dir=os.environ['INTOGEN_DATASETS']+'/liftover')

def parse(file):

    for m in TSVReader(file):
        _, sample, ref, alt = m['#Uploaded_variation'].split('__')
        chromosome, position = m['Location'].split(':')

        # FIXME variant type is always false
        variant_type = None
        if ref == '-':
            variant_type == "INS"
        elif alt == '-':
            variant_type == "DEL"
        elif len(ref) == len(alt) and len(ref) == 1:
            variant_type == "SNP"
        elif len(ref) == len(alt) and len(ref) == 2:
            variant_type == "DNP"
        elif len(ref) == len(alt) and len(ref) == 2:
            variant_type == "TNP"
        else:
            continue

        strand = '-' if m['STRAND'] == '-1' else '+'
        hg19_position = LIFTOVER.convert_coordinate("chr{}".format(chromosome), int(position) - 1, strand)
        if hg19_position is None or len(hg19_position) != 1:
            continue
        position = hg19_position[0][1] + 1

        fields = [
            m['SYMBOL'],
            chromosome,
            str(position),
            str(position),  # TODO should we change for indels?
            m['STRAND'],  # TODO as everything is in positive strand, does it matter? Does VEP change the strand?
            m['Consequence'],
            variant_type,
            ref,
            ref,
            alt,
            sample
        ]
        yield fields
