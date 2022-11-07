# for loading/processing the images
# for everything else
import os
import pickle

import matplotlib.pyplot as plt
import numpy as np
# models
from keras.applications.vgg16 import VGG16
from keras.applications.vgg16 import preprocess_input
from keras.models import Model
# clustering and dimension reduction
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from tensorflow.keras.utils import load_img
from tqdm import tqdm

path = r"/home/luca/mismas/BBC News/object_thumbnails"
# change the working directory to the path where the images are located
os.chdir(path)

# this list holds all the image filename
flowers = []

# creates a ScandirIterator aliased as files
with os.scandir(path) as files:
    # loops through each file in the directory
    for file in files:
        if file.name.endswith('.jpg'):
            # adds only the image files to the flowers list
            flowers.append(file.name)

# flowers = flowers[:1000]

model = VGG16()
model = Model(inputs=model.inputs, outputs=model.layers[-2].output)


def extract_features(file, model):
    # load the image as a 224x224 array
    img = load_img(file, target_size=(224, 224))
    # convert from 'PIL.Image.Image' to numpy array
    img = np.array(img)
    # reshape the data for the model reshape(num_of_samples, dim 1, dim 2, channels)
    reshaped_img = img.reshape(1, 224, 224, 3)
    # prepare image for model
    imgx = preprocess_input(reshaped_img)
    # get the feature vector
    features = model.predict(imgx, use_multiprocessing=True)
    return features


data = {}
p = r"/home/luca/mismas/BBC News"

# lop through each image in the dataset
for flower in tqdm(flowers):
    # try to extract the features and update the dictionary
    try:
        feat = extract_features(flower, model)
        data[flower] = feat
    # if something fails, save the extracted features as a pickle file (optional)
    except:
        with open(p, 'wb') as file:
            pickle.dump(data, file)

# get a list of the filenames
filenames = np.array(list(data.keys()))

# get a list of just the features
feat = np.array(list(data.values()))

# reshape so that there are 210 samples of 4096 vectors
feat = feat.reshape(-1, 4096)

# get the unique labels (from the flower_labels.csv)
label = [i for i in range(1, 20)]
unique_labels = list(set(label))

# reduce the amount of dimensions in the feature vector
pca = PCA(n_components=100, random_state=22)
pca.fit(feat)
x = pca.transform(feat)

# cluster feature vectors
kmeans = KMeans(n_clusters=len(unique_labels), random_state=22)
kmeans.fit(x)

# holds the cluster id and the images { id: [images] }
groups = {}
for file, cluster in zip(filenames, kmeans.labels_):
    if cluster not in groups.keys():
        groups[cluster] = []
        groups[cluster].append(file)
    else:
        groups[cluster].append(file)

# sort the clusters by from largest to smallest
groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
# renameke keys as "cluster 1", "cluster 2", etc.
sorted_groups = {}
for i, (key, value) in enumerate(groups):
    sorted_groups[i] = (f"cluster {i}", value)

import json

with open('clusters.json', 'w') as file:
    json.dump(sorted_groups, file)


# function that lets you view a cluster (based on identifier)
def view_cluster(cluster):
    plt.figure(figsize=(25, 25));
    # gets the list of filenames for a cluster
    files = groups[cluster][1]
    # only allow up to 30 images to be shown at a time
    if len(files) > 30:
        print(f"Clipping cluster size from {len(files)} to 30")
        files = files[:29]
    # plot each image in the cluster
    for index, file in enumerate(files):
        plt.subplot(10, 10, index + 1);
        img = load_img(file)
        img = np.array(img)
        plt.imshow(img)
        plt.axis('off')
    plt.show()


# this is just incase you want to see which value for k might be the best
sse = []
list_k = list(range(3, 100))
from tqdm import tqdm

for k in tqdm(list_k, desc="Finding best k"):
    km = KMeans(n_clusters=k, random_state=22)
    km.fit(x)

    sse.append(km.inertia_)

# Plot sse against k
plt.figure(figsize=(6, 6))
plt.plot(list_k, sse)
plt.xlabel(r'Number of clusters *k*')
plt.ylabel('Sum of squared distance')
for i, cluster in enumerate(groups):
    view_cluster(i)
