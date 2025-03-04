from setuptools import setup, find_packages

setup(
    name='continual_rl',
    version='1.0',
    description='Continual reinforcement learning baselines and standard experiments.',
    author='Sam Powers',
    author_email='snpowers@cs.cmu.edu',
    packages=find_packages(),
    py_modules=['continual_rl.available_policies', 'continual_rl.experiment_specs'],
    install_requires=['setuptools',
                      'uuid',
                      'numpy',
                      'tensorboard',
                      'torch-ac',
                      'gymnasium[atari]',
                      'gymnasium[accept-rom-license]',
                      'ale_py'
                      'dotmap',
                      'psutil',
                      'opencv-python',
                      # NOTE: More recent versions of imageio can't seem to save single 
                      #       color channel images. This means when tensorboard goes to 
                      #       save images for videos, imageio 'ValueError: Can't write images
                      #        with one color channel' is thrown. Root issue is with moviepy
                      #        but installing older imageio version seems to get around it.
                      'imageio==2.24.0',
                      'moviepy'
                    ]
)
