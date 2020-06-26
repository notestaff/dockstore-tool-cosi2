#!/usr/bin/env python3

# * Preamble

"""Run cosi2 simulation for one block"""

# * imports

import argparse
import collections
import concurrent.futures
import contextlib
import functools
import gzip
import io
import json
import os
import random
import subprocess
import sys

# * Utils

def dump_file(fname, value):
    """store string in file"""
    with open(fname, 'w')  as out:
        out.write(str(value))

def _pretty_print_json(json_val, sort_keys=True):
    """Return a pretty-printed version of a dict converted to json, as a string."""
    return json.dumps(json_val, indent=4, separators=(',', ': '), sort_keys=sort_keys)

def _write_json(fname, json_val):
    dump_file(fname=fname, value=_pretty_print_json(json_val))

def _load_dict_sorted(d):
    return collections.OrderedDict(sorted(d.items()))

def _json_loads(s):
    return json.loads(s.strip(), object_hook=_load_dict_sorted, object_pairs_hook=collections.OrderedDict)

def _json_loadf(fname):
    return _json_loads(slurp_file(fname))


def slurp_file(fname, maxSizeMb=50):
    """Read entire file into one string.  If file is gzipped, uncompress it on-the-fly.  If file is larger
    than `maxSizeMb` megabytes, throw an error; this is to encourage proper use of iterators for reading
    large files.  If `maxSizeMb` is None or 0, file size is unlimited."""
    fileSize = os.path.getsize(fname)
    if maxSizeMb  and  fileSize > maxSizeMb*1024*1024:
        raise RuntimeError('Tried to slurp large file {} (size={}); are you sure?  Increase `maxSizeMb` param if yes'.
                           format(fname, fileSize))
    with open_or_gzopen(fname) as f:
        return f.read()

def open_or_gzopen(fname, *opts, **kwargs):
    mode = 'r'
    open_opts = list(opts)
    assert type(mode) == str, "open mode must be of type str"

    # 'U' mode is deprecated in py3 and may be unsupported in future versions,
    # so use newline=None when 'U' is specified
    if len(open_opts) > 0:
        mode = open_opts[0]
        if sys.version_info[0] == 3:
            if 'U' in mode:
                if 'newline' not in kwargs:
                    kwargs['newline'] = None
                open_opts[0] = mode.replace("U","")

    # if this is a gzip file
    if fname.endswith('.gz'):
        # if text read mode is desired (by spec or default)
        if ('b' not in mode) and (len(open_opts)==0 or 'r' in mode):
            # if python 2
            if sys.version_info[0] == 2:
                # gzip.open() under py2 does not support universal newlines
                # so we need to wrap it with something that does
                # By ignoring errors in BufferedReader, errors should be handled by TextIoWrapper
                return io.TextIOWrapper(io.BufferedReader(gzip.open(fname)))

        # if 't' for text mode is not explicitly included,
        # replace "U" with "t" since under gzip "rb" is the
        # default and "U" depends on "rt"
        gz_mode = str(mode).replace("U","" if "t" in mode else "t")
        gz_opts = [gz_mode]+list(opts)[1:]
        return gzip.open(fname, *gz_opts, **kwargs)
    else:
        return open(fname, *open_opts, **kwargs)

# * run_one_sim

def run_one_replica(args, paramFile, replicaNum):
    """Run one cosi2 replica; return a ReplicaInfo struct (defined in Dockstore.wdl)"""

    randomSeed = random.SystemRandom().randint(0, 2147483646)

    tpedPrefix = f"{args.simBlockId}_rep{replicaNum}"
    trajFile = f"{args.simBlockId}.{replicaNum}.traj"
    sweepInfoFile = f"sweepinfo.{replicaNum}.tsv"
    _run = functools.partial(subprocess.check_call, shell=True)
    emptyFile = f"empty.rep{replicaNum}"
    dump_file(emptyFile, '')
    cosi2_cmd = (
        f'(env COSI_NEWSIM=1 COSI_MAXATTEMPTS={args.maxAttempts} COSI_SAVE_TRAJ={trajFile} '
        f'COSI_SAVE_SWEEP_INFO={sweepInfoFile} coalescent -R {args.recombFile} -p {paramFile} '
        f'-v -g -r {randomSeed} --genmapRandomRegions '
        f'--drop-singletons .25 --tped {tpedPrefix} )'
        )
    try:
        _run(cosi2_cmd)
        # TODO: parse param file for list of pops, and check that we get all the files.
        tpeds_tar_gz = f"{args.simBlockId}.{replicaNum}.tpeds.tar.gz"
        _run(f'tar cvfz {tpeds_tar_gz} {tpedPrefix}_*.tped')
        simNum, selPop, selGen, selBegPop, selBegGen, selCoeff, selFreq = map(float, slurp_file(sweepInfoFile).strip().split())
        replicaInfo = dict(modelId=args.modelId, blockNum=args.blockNum,
                           replicaNum=replicaNum, succeeded=True, randomSeed=randomSeed,
                           tpeds=tpeds_tar_gz, traj=trajFile, selPop=int(selPop), selGen=selGen, selBegPop=int(selBegPop),
                           selBegGen=selBegGen, selCoeff=selCoeff, selFreq=selFreq)
    except subprocess.SubprocessError:
        failed_replica_info = dict(modelId=args.modelId, blockNum=args.blockNum,
                                   replicaNum=replicaNum, succeeded=False, randomSeed=randomSeed,
                                   tpeds=emptyFile, traj=emptyFile, selPop=0, selGen=0., selBegPop=0,
                                   selBegGen=0., selCoeff=0., selFreq=0.)
        # TODO: save sampled params even if sim fails
        replicaInfo = failed_replica_info
    return replicaInfo

# * main

def do_main():
    """Parse args and run cosi"""


    parser = argparse.ArgumentParser()

    parser.add_argument('--paramFileCommon', required=True, help='the common part of all parameter files')
    parser.add_argument('--paramFile', required=True, help='the variable part of all parameter files')
    parser.add_argument('--recombFile', required=True, help='the recombination file')
    parser.add_argument('--modelId', required=True, help='demographic model id')
    parser.add_argument('--simBlockId', required=True, help='string ID of the simulation block')
    parser.add_argument('--blockNum', type=int, required=True, help='number of the block of simulations')
    parser.add_argument('--numSimsInBlock', type=int, required=True, help='number of replicas in the block')
    parser.add_argument('--maxAttempts', type=int, required=True,
                        help='max # of times to try simulating forward frequency trajectory before giving up')

    parser.add_argument('--outJson', required=True, help='write output json to this file')
    args = parser.parse_args()

    paramFileCombined = 'paramFileCombined.par'
    dump_file(fname=paramFileCombined, value=slurp_file(args.paramFileCommon)+slurp_file(args.paramFile))

    _write_json(args.outJson,
                dict(replicaInfos=[run_one_replica(args=args,
                                                   paramFile=paramFileCombined,
                                                   replicaNum=replicaNum)
                                   for replicaNum in range(args.numSimsInBlock)]))
    
if __name__ == '__main__':
    do_main()
