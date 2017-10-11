import os
import gzip
import csv
import logging
import click

from functools import partial
from bgparsers import selector
from concurrent.futures import ProcessPoolExecutor

from tasks.oncodriveclust import OncodriveClustTask
from tasks.oncodrivefml import OncodriveFmlTask
from tasks.oncodriveomega import OncodriveOmegaTask
from tasks.hotmaps import HotmapsTask
from tasks.vep import VepTask
from tasks.mutsigcv import MutsigCvTask
from tasks.schulze import SchulzeTask

from filters.base import VariantsReader
from filters.preprocess import PreprocessFilter


TASKS = {t.KEY: t for t in [
    VepTask,
    OncodriveFmlTask,
    OncodriveOmegaTask,
    OncodriveClustTask,
    HotmapsTask,
    MutsigCvTask,
    SchulzeTask
]}


CONFIG = {
    VepTask.KEY: {'conda_env': os.environ['CONDA_ENV'], 'vep_data': os.environ['VEP_DATA']},
    OncodriveFmlTask.KEY: {'config_file': os.environ['ONCODRIVEFML_CONF']},
    OncodriveOmegaTask.KEY: {'config_file': os.environ['ONCODRIVEOMEGA_CONF']},
    HotmapsTask.KEY: {'conda_env': 'hotmaps', 'method_folder': os.environ['HOTMAPS_METHOD']}
}

logger = logging.getLogger('intogen')
LOG_FILE = 'intogen.log'
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


def read_file(group_key, tsv_file):
    with gzip.open(tsv_file, "rt") as fd:
        reader = csv.DictReader(fd, delimiter='\t')
        for row in reader:
            yield row


def prepare_task(reader, tasks, item):
    position, (group_key, group_data) = item

    # Initialize task name
    [t.init(group_key) for t in tasks]

    # Input start
    [t.input_start() for t in tasks]

    # Input write
    for i, mut in enumerate(reader(group_key, group_data)):
        id = "I{:010d}".format(i)
        for t in tasks:
            t.input_write(id, mut)

    # Input close
    [t.input_end() for t in tasks]

    return [(t.KEY, group_key) for t in tasks]


def prepare_tasks(groups, reader, tasks, cores=None):
    func = partial(prepare_task, reader, tasks)

    all_tasks = []
    if cores > 1:
        with ProcessPoolExecutor(cores) as executor:
            for tasks in executor.map(func, enumerate(groups)):
                all_tasks += tasks
    else:
        for tasks in map(func, enumerate(groups)):
            all_tasks += tasks

    return all_tasks


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('--debug', is_flag=True, help='Enable debugging')
@click.version_option()
def cli(debug):
    if debug:
        fmt = logging.Formatter('%(asctime)s %(message)s', datefmt='%H:%M:%S')
        fh = logging.FileHandler(LOG_FILE, 'w')
        fh.setLevel(logging.DEBUG if debug else logging.INFO)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.setLevel(logging.DEBUG)
        logger.debug('Debug mode enabled')


@click.command(short_help='Create tasks input files')
@click.option('--input', '-i', required=True, help="Input file or folder", type=click.Path())
@click.option('--output', '-o', required=True, help="Output folder")
@click.option('--groupby', '-g', default="DATASET", type=str, help="Input data group by field")
@click.option('--cores', default=os.cpu_count(), type=int, help="Maximum groups to process in parallel")
@click.argument('tasks', nargs=-1)
def preprocess(input, output, groupby, cores, tasks):
    groups = selector.groupby(input, by=groupby)
    groups = list(groups)
    tasks = [TASKS[t](output, CONFIG) for t in tasks]

    reader = VariantsReader()
    filter = PreprocessFilter(reader)

    prepare_tasks(groups, filter.run, tasks, cores=cores)


@click.command(short_help='Create tasks input files')
@click.option('--input', '-i', required=True, help="Input file or folder", type=click.Path())
@click.option('--output', '-o', required=True, help="Output folder")
@click.argument('tasks', nargs=-1)
def read(input, output, tasks):
    tasks = [TASKS[t](output, CONFIG) for t in tasks]
    group_key = os.path.basename(input).split('.')[0]
    prepare_tasks([(group_key, input)], read_file, tasks, cores=1)


@click.command(short_help='Run a task')
@click.option('--output', '-o', default="output", type=click.Path(), help="Output folder")
@click.argument('task', type=str)
@click.argument('key', type=str)
def run(output, task, key):
    task = TASKS[task](output, CONFIG)
    task.init(key)
    task.run()


cli.add_command(preprocess)
cli.add_command(read)
cli.add_command(run)


if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S', level=logging.INFO)
    cli()
