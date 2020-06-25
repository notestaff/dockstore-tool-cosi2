"""Run cosi2 simulation for one block"""

import argparse
import collections
import gzip
import io
import json
import os
import random
import subprocess
import sys

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

def do_main():
    """Parse args and run cosi"""


    parser = argparse.ArgumentParser()
    parser.add_argument('params_json')
    parser.add_argument('out_json')
    args_tmp = parser.parse_args()
    args = _json_loadf(args_tmp.params_json)
    print(_pretty_print_json(args))
    dump_file('tpeds.dummy', 'no-tpeds')
    _write_json(args_tmp.out_json, dict(replicaInfos=[dict(modelId=args['modelId'], blockNum=args['blockNum'],
                                                           replicaNum=0, succeeded=False, randomSeed=239,
                                                           tpeds='tpeds.dummy', traj='tpeds.dummy', selPop=1, selGen=0., selBegPop=1,
                                                           selBegGen=0., selCoeff=.02, selFreq=.33)]))
    
    #parser.add_argument('--paramFileCommon', dest='param_file_common', required=True, help='the common part of all parameter files')
    # parser.add_argument('--paramFile', dest='param_file', required=True, help='the variable part of all parameter files')
    # parser.add_argument('--recombFile', dest='recomb_file', required=True, help='the recombination file')
    # parser.add_argument('--modelId', dest='model_id', required=True, help='demographic model id')
    # parser.add_argument('--simBlockId', dest='sim_block_id', required=True, help='string ID of the simulation block')
    # parser.add_argument('--blockNum', dest='block_num', type=int, required=True, help='number of the block of simulations')
    # parser.add_argument('--maxAttempts', dest='max_attempts', type=int, required=True,
    #                     help='max # of times to try simulating forward frequency trajectory before giving up')
    # parser.add_argument('--randomSeed', dest='random_seed', type=int, required=True,
    #                     help='random seed to use, or 0 to choose one')
    
    
    

if __name__ == '__main__':
    do_main()
