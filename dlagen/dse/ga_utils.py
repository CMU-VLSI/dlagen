import random
import numpy as np

def mutate_single_config(individual, max_list):
    # randomly change one config
    index = random.randint(0, len(individual)-1)
    individual[index] = random.randint(0, max_list[index])
    return (individual,)

def initIndividual(icls, max_list):
    config = []
    for i in range(len(max_list)):
        config += [random.randint(0, max_list[i])]
    return icls(config)

def get_avg(x):
    x = np.array(x)[:, 0]
    means = np.mean(x).tolist()
    return means

def get_std(x):
    x = np.array(x)[:, 0]
    stds = np.std(x).tolist()
    return stds

def get_min(x):
    x = np.array(x)[:, 0]
    mins = np.min(x).tolist()
    return mins

def report_min(x):
    x = np.array(x)
    min_index = np.argmin(x[:, 0])
    mins = x[min_index].tolist()
    return mins

def report_max(x):
    x = np.array(x)
    max_index = np.argmax(x[:, 0])
    maxs = x[max_index].tolist()
    return maxs

def get_max(x):
    x = np.array(x)[:, 0]
    maxs = np.max(x).tolist()
    return maxs