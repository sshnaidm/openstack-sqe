#!/usr/bin/env python
import os
import yaml

from config import opts, ConfigError, TOPO_PATH
from cloud import Lab


def main():
    if opts.topology:
        with open(os.path.join(TOPO_PATH, opts.topology + "_topology.yaml")) as f:
            topo_config = yaml.load(f)
    elif opts.topoconf:
        topo_config = yaml.load(opts.topoconf)
    else:
        raise ConfigError("Please provide topology!")

    lab = Lab(
        opts.lab_id,
        topo_config,
        opts.img_dir,
        opts.boot,
        opts.cloud_img_path,
        opts.ipv
    )
    if not opts.undefine_all and not opts.shutdown_all:
        lab.destroy()
        lab.setup()
    elif opts.undefine_all:
        lab.destroy()
    elif opts.shutdown_all:
        lab.shutdown()


if __name__ == "__main__":
    main()
