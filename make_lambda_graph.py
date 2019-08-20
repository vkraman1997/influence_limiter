
from classes.preprocessor import Preprocessor
from classes.il_recsys import ILRecSys

import numpy as np
import sys
import matplotlib.pyplot as plt

from functions.attack import *
from functions.utility import *
from random import shuffle

import yaml
import os

YAML_FILE = "./config/shills.yml"
with open(YAML_FILE, 'r') as file:
    y_d = yaml.load(file)

dataset = y_d["dataset"]
data_file = y_d["paths"][ dataset]["ratings"]

print("----Dataset Details----")
print(f"Dataset: {dataset}")

# Preprocess data
data_class = Preprocessor(data_file, dataset)

if y_d["clean"]["type_of"] == "percent":
    alpha_i = y_d["clean"]["alpha_i"]
    alpha_u = y_d["clean"]["alpha_u"]
    data_class.percentage_cleaning(percent=y_d["clean"]["percent"], alpha_i=alpha_i, alpha_u=alpha_u)
    print("Cleaning Strategy: Percentage")
    print(f'Cleaning Percentage: {y_d["clean"]["percent"]}')
    print(f"Cleaning Params: {alpha_i} {alpha_u}")
elif y_d["clean"]["type_of"] == "threshold":
    min_items = y_d["clean"]["min_items"]
    min_users = y_d["clean"]["min_users"]
    data_class.threshold_cleaning(min_items=min_items, min_users=min_users)
    print("Cleaning Strategy: Threshold")
    print(f"Cleaning Params: {min_items} {min_users}")
else:
    print("ERROR: cleaning not recognized, won't clean")

data_class.print_stats()



print("----Experiment Details----")

c = y_d["c_"]
n = y_d["n_"]
t_user = y_d["tracked_user"]
print(f"Target User: {t_user}")
# Separate data into initialization and heldout
heldout_data = data_class.get_heldout_data(users=[t_user], no_users=0, min_no=0, percentage=0.0)
entry_list = data_class.return_ratings_list()

# Initialize recommender system
recsys = ILRecSys(entry_list, black_box="knn", params={"corr": "pearson", "strat": "top_k", "param": 10}, 
                  n=n, c=c, loss_type="squared", tracked_user=t_user)

# Add attack
attack_ratings = []
n_targets = y_d["attack"]["no_targets"]
target_items = {entry[1] for entry in heldout_data[-n_targets:] }
attack_ids = set()
# cloned_users = [308, 194, 303, 234, 95, 7, 130]
cloned_users = y_d["attack"]["cloned"]
no_items = y_d["attack"]["no_ratings"]
t_rating = y_d["attack"]["t_rating"]
print(f'Attack Type: {y_d["attack"]["type_of"]}')
print(f'No. Attackers: {y_d["attack"]["no_attackers"]}')
for i in range(y_d["attack"]["no_attackers"]):
    if y_d["attack"]["type_of"] == "clone":
        attack = create_clone_attack(recsys, copied_user=cloned_users[i % len(cloned_users)], 
                                     clone_id=-i, t_items=target_items, t_rating=t_rating)
    elif y_d["attack"]["type_of"] == "random":
        attack = create_random_attack(recsys, no_items=no_items, clone_id=-i, t_items=target_items, t_rating=t_rating)
    elif y_d["attack"]["type_of"] == "determ":
        attack = create_determ_attack(recsys, no_items=no_items, clone_id=-i, t_items=target_items, t_rating=t_rating)
    else:
        print("Error, attack type not recognized. won't attack")
        break
    attack_ratings.extend(attack)
    attack_ids.add(-i)

# Establish order for ratings in system
place_attack = y_d["attack"]["place_attack"]
print(f"Attackers Place: {place_attack}")
if place_attack == "first":
    # Attackers will go before others w.r.t. timestamps
    # Has to delete all timestamps in normal ratings
    entry_list = [ [entry[0], entry[1], entry[2], time()] for entry in entry_list ]
    entry_list.extend(attack_ratings)
    entry_list.reverse()
elif place_attack == "last":
    # Don't have to do anything
    # attack_ratings = [[entry[0], entry[1], entry[2], time()] for entry in attack_ratings ]
    entry_list.extend(attack_ratings)
elif place_attack == "random":
    # Has to extend, then recreate
    entry_list.extend(attack_ratings) 
    shuffle(entry_list)
    entry_list = [ [entry[0], entry[1], entry[2], time()] for entry in entry_list ]

# Establish order for heldout ratings

place_target = y_d["attack"]["place_target"]
if place_target == "first":
    # Attackers will go before others w.r.t. timestamps
    # Has to delete all timestamps in normal ratings
    heldout_data.reverse()
elif place_target == "last":
    # Don't have to do anything
    pass
elif place_target == "random":
    # Has to extend, then recreate 
    shuffle(heldout_data)


base_path = "./figures/" + y_d["attack"]["type_of"] + "_" + str(y_d["attack"]["no_attackers"]) + "_" + \
                 place_attack + "_" + str(n_targets) + "_" + place_target + "/"

if not os.path.exists(base_path):
    os.makedirs(base_path)



cs = [1, 2, 5, 10, 20, 40, 50, 100, 200, 500, 1000, 10000, 100000, 1000000, 10000000, 100000000]

il_graph = []
nil_graph = []
t_il_graph = []
t_nil_graph = []

for run in range(1):
    # shuffle(heldout_data)
    curr_il_graph = []
    curr_nil_graph = []
    curr_t_il_graph = []
    curr_t_nil_graph = []
    for c in cs:
        # Remake RecSys with attack ids
        recsys = ILRecSys(entry_list, black_box="knn", params={"corr": "pearson", "strat": "top_k", "param": 30}, 
                          n=n, c=c, loss_type="squared", tracked_user=t_user)

        # Run experiment once
        il_accs, nil_accs, t_il_accs, t_nil_accs, losses_diff, recsys  = run_experiment(recsys, heldout_data, attack_id=attack_ids, t_items=target_items)
        curr_il_graph.append(il_accs[-1])
        curr_nil_graph.append(nil_accs[-1])
        curr_t_il_graph.append(t_il_accs[-1])
        curr_t_nil_graph.append(t_nil_accs[-1])

        print("done with c {}".format(c))

    if len(il_graph) > 0:
        il_graph += (1 / (run + 1))*(curr_il_graph - il_graph)
        nil_graph += (1 / (run + 1))*(curr_nil_graph - nil_graph)
        t_il_graph += (1 / (run + 1))*(curr_t_il_graph - t_il_graph)
        t_nil_graph += (1 / (run + 1))*(curr_t_nil_graph - t_nil_graph)
    else:
        il_graph = curr_il_graph
        nil_graph = curr_nil_graph
        t_il_graph = curr_t_il_graph
        t_nil_graph = curr_t_nil_graph

fig_path = "./figures/" + y_d["attack"]["type_of"] + "/"

if not os.path.exists(fig_path):
    os.makedirs(fig_path)


# Plot Target Item Accuracy
# Acc Graph
plt.figure(2)
x = np.log(np.asarray(cs))
plt.plot(x, il_graph, color='r', label='IL')
plt.plot(x, nil_graph, color='b', label='Non-IL')
plt.xlabel(r"$\lambda$ Value")
plt.ylabel("Average Accuracy")
plt.legend()
plt.title("Recommendation Accuracy")
plt.savefig(fig_path + "lambda_all.png")
plt.clf()


# Plot Target Item Accuracy
# Acc Graph
plt.figure(2)
x =  np.log(np.asarray(cs))
plt.plot(x, t_il_graph, color='r', label='IL')
plt.plot(x, t_nil_graph, color='b', label='Non-IL')
plt.xlabel(r"$\lambda$ Value")
plt.ylabel("Average Accuracy")
plt.legend()
plt.title("Recommendation Accuracy for Targeted Items")
plt.savefig(fig_path + "lambda_target.png")
plt.clf()
