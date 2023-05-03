import spotify_utils
import tree_utils
import pandas as pd
from sklearn.tree import DecisionTreeClassifier,_tree
from os import system
import numpy as np
import ctypes

POSITIVE_PLAYLIST_ID = '76VEUM2sKenxND7iHc4mW9'
NEGATIVE_PLAYLIST_ID = '7Bhjl9pVtBXfbuoBls1OCy'
TEST_PLAYLIST_ID = '0paEEsl7MGgvaOh2cQaf2C'
POSITIVE_PREDICTION_PLAYLIST_ID = '2FAYQpkj1MaaqAPZ37L8TF'
NEGATIVE_PREDICTION_PLAYLIST_ID = '5dt0FyyyXjv6F6dJK6QYcA'
PREDICT_PROBA_PLAYLIST_ID       = '1fsOQ70bmDJatDQETHBUnf'

audio_features_to_use = ["acousticness","danceability","energy","liveness","loudness","speechiness","tempo","valence","duration"]

def clear_terminal():
    system("cls")

def open_spotify():
    system("start spotify")


# See http://msdn.microsoft.com/library/default.asp?url=/library/en-us/winprog/winprog/windows_api_reference.asp
# for information on Windows APIs.
STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE= -11
STD_ERROR_HANDLE = -12

FOREGROUND_BLUE = 0x01 # text color contains blue.
FOREGROUND_GREEN= 0x02 # text color contains green.
FOREGROUND_RED  = 0x04 # text color contains red.
FOREGROUND_INTENSITY = 0x08 # text color is intensified.
BACKGROUND_BLUE = 0x10 # background color contains blue.
BACKGROUND_GREEN= 0x20 # background color contains green.
BACKGROUND_RED  = 0x40 # background color contains red.
BACKGROUND_INTENSITY = 0x80 # background color is intensified.


std_out_handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

def set_color(color, handle=std_out_handle):
    """(color) -> BOOL
    
    Example: set_color(FOREGROUND_GREEN | FOREGROUND_INTENSITY)
    """
    bool = ctypes.windll.kernel32.SetConsoleTextAttribute(handle, color)
    return bool
# set_color

# based on https://mljar.com/blog/extract-rules-decision-tree/
def tree_to_code(tree, object_name, test_name, feature_names, class_names):
    tree_ = tree.tree_
    feature_name = [
        feature_names[i] if i != _tree.TREE_UNDEFINED else "undefined!"
        for i in tree_.feature
    ]
    feature_names = [f.replace(" ", "_") for f in feature_names]
    print(f"def {test_name}(track):")

    def recurse(node, depth):
        indent = "    " * depth
        if tree_.feature[node] != _tree.TREE_UNDEFINED:
            name = feature_name[node]
            threshold = tree_.threshold[node]
            print(f"{indent}if {object_name}.{name} <= {threshold:.2f}:")
            recurse(tree_.children_left[node], depth + 1)
            print(f"{indent}else:")
            recurse(tree_.children_right[node], depth + 1)
        else:
            node_value = tree_.value[node][0]
            class_index = np.argmax(node_value)
            class_value = bool(class_index)
            class_name = class_names[class_index]
            print(f"{indent}return {class_value} # It's {class_name}!")

    recurse(0, 1)

def retrain_model(sp,coder_name):
    # Get the training data
    input(f"Sending the Spotify training playlists to {coder_name}...")
    positives = spotify_utils.get_playlist_tracks(sp,POSITIVE_PLAYLIST_ID,audio_features=True)
    positives["is_beatles"] = True
    negatives = spotify_utils.get_playlist_tracks(sp,NEGATIVE_PLAYLIST_ID,audio_features=True)
    if negatives is None:
        training_data = positives
        single_class = True
    else:
        negatives["is_beatles"] = False
        training_data = pd.concat([positives,negatives])
        single_class = False

    # Train a Decision Tree Classifier
    X_train = training_data[audio_features_to_use]
    y_train = training_data["is_beatles"]
    model = DecisionTreeClassifier(random_state=0)
    model.fit(X_train, y_train)
    input(f"Waiting for {coder_name}'s response...")
    
    # Test the model
    input(f"Using's {coder_name}'s code to predict our test playlists...")
    test_data = spotify_utils.get_playlist_tracks(sp,TEST_PLAYLIST_ID,audio_features=True)
    X_test = test_data[audio_features_to_use]
    y_pred = model.predict(X_test)
    test_data["is_beatles"] = y_pred.astype(bool)
    if not single_class:
        test_data["predict_proba"] = model.predict_proba(X_test)[:,1]
        test_data.sort_values(by="predict_proba",ascending=False,inplace=True)
    spotify_utils.overwrite_playlist(sp,POSITIVE_PREDICTION_PLAYLIST_ID,test_data[test_data["is_beatles"] == True])
    spotify_utils.overwrite_playlist(sp,NEGATIVE_PREDICTION_PLAYLIST_ID,test_data[test_data["is_beatles"] == False])
    spotify_utils.overwrite_playlist(sp,PREDICT_PROBA_PLAYLIST_ID,test_data)

    open_spotify()

    input(f"Let's inspect {coder_name} code...")
    clear_terminal()
    set_color(FOREGROUND_GREEN | FOREGROUND_INTENSITY)
    tree_to_code(model,"track","is_beatles",audio_features_to_use,["Not The Beatles","The Beatles"])
    set_color(FOREGROUND_GREEN | FOREGROUND_RED | FOREGROUND_BLUE)

if __name__ == '__main__':
    input("Press Enter to start...")
    clear_terminal()
    name = input("What's our coder's name?")
    while True:
        sp = spotify_utils.spotify_connect()
        retrain_model(sp,name)
        input("Press Enter to retrain...")
        clear_terminal()