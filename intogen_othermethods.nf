#!/usr/bin/env nextflow

OUTPUT = file(params.output)


OUT_VEP = Channel.fromPath( OUTPUT + '/vep/*.out.gz' )
process PreprocessFromVep {
    tag { task_file.fileName }

    publishDir OUTPUT, mode: 'copy'
    afterScript "cp .command.log $OUTPUT/preprocess_from_vep.log"

    input:
        val task_file from OUT_VEP

    output:
        file "oncodriveomega/*.in.gz" into IN_ONCODRIVEOMEGA mode flatten
        file "mutsigcv/*.in.gz" into IN_MUTSIGCV mode flatten
        file "edriver/*.in.gz" into IN_EDRIVER mode flatten

    """
    python $baseDir/intogen4.py read -i $task_file -o . oncodriveomega mutsigcv edriver
    """
}

process OncodriveOmega {
    tag { task_file.fileName }
    publishDir OUTPUT, mode: 'copy'

    when:
        params.omega

    input:
        val task_file from IN_ONCODRIVEOMEGA



    output:
        file "oncodriveomega/*.out.gz" into OUT_ONCODRIVEOMEGA mode flatten

    """
    if [ ! -f "${outputFile(OUTPUT, 'oncodriveomega', task_file)}" ]
    then
        export PROCESS_CPUS=$task.cpus
        python $baseDir/intogen4.py run -o . oncodriveomega $task_file
    else
        mkdir -p ./oncodriveomega && cp ${outputFile(OUTPUT, 'oncodriveomega', task_file)} ./oncodriveomega/
    fi
    """
}

process MutsigCV {
    tag { task_file.fileName }
    publishDir OUTPUT, mode: 'copy'

    when:
        params.mutsigcv

    input:
        val task_file from IN_MUTSIGCV

    output:
        file "mutsigcv/*.out.gz" into OUT_MUTSIGCV mode flatten

    """
    if [ ! -f "${outputFile(OUTPUT, 'mutsigcv', task_file)}" ]
    then
        python $baseDir/intogen4.py run -o . mutsigcv $task_file
    else
        mkdir -p ./mutsigcv && cp ${outputFile(OUTPUT, 'mutsigcv', task_file)} ./mutsigcv/
    fi
    """
}

process EDriver {
    tag { task_file.fileName }
    publishDir OUTPUT, mode: 'copy'

    when:
        params.edriver

    input:
        val task_file from IN_EDRIVER

    output:
        file "edriver/*.out.gz" into OUT_EDRIVER mode flatten

    """
    if [ ! -f "${outputFile(OUTPUT, 'edriver', task_file)}" ]
    then
        python $baseDir/intogen4.py run -o . edriver $task_file
    else
        mkdir -p ./edriver && cp ${outputFile(OUTPUT, 'edriver', task_file)} ./edriver/
    fi
    """
}

def outputFile(output_folder, process_folder, task_file) {
    return output_folder.toString() + '/' + process_folder + '/' + task_file.fileName.toString().replace('.in.gz', '.out.gz')
}