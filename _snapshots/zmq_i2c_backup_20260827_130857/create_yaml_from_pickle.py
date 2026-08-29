import yaml
import pickle
import sys
import click


@click.command()
@click.argument('pickled_config',
              type=click.File('rb'))
@click.argument('yaml_config',
              type=click.File('w+'))
def pickled_config_to_yaml(pickled_config, yaml_config):
    """
    Program to transform the register description of the ROC into a yaml file

    PICKLED_CONFIG is the path to the pickled configuration
    YAML_CONFIG is the path to the produced yaml configuration
    """
    yaml_config.write(yaml.dump(pickle.load(pickled_config)))

if __name__ == "__main__":
    pickled_config_to_yaml()
