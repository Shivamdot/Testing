import time
import cv2
import numpy as np
import tensorflow as tf
from process.yolov3_tf2.models import YoloV3
from process.yolov3_tf2.dataset import transform_images, load_tfrecord_dataset
from process.yolov3_tf2.utils import draw_outputs, draw_output
import os

from sklearn.cluster import KMeans

from process.init import yolo, class_names
size = 416


def hsv(clr):
    r = clr[0]
    g = clr[1]
    b = clr[2]
    r, g, b = r/255.0, g/255.0, b/255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx-mn
    if mx == mn:
        h = 0
    elif mx == r:
        h = (60 * ((g-b)/df) + 360) % 360
    elif mx == g:
        h = (60 * ((b-r)/df) + 120) % 360
    elif mx == b:
        h = (60 * ((r-g)/df) + 240) % 360
    if mx == 0:
        s = 0
    else:
        s = (df/mx)*100
    v = mx*100

    return [int(h), int(s), int(v)]

def orb_feature(img, sides, caseID):
    query_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  
    
    outcome = []

    for side in sides:
        image_path = "./static/images/{}/{}.jpg".format(caseID,side)
        train_img = cv2.imread(image_path)
        train_img = cv2.cvtColor(train_img, cv2.COLOR_BGR2GRAY)

        orb = cv2.ORB_create(5000, 2.0)
        try:
            keypoints_train, descriptors_train = orb.detectAndCompute(train_img, None)
            keypoints_query, descriptors_query = orb.detectAndCompute(query_img, None)
            
            total_keys = len(keypoints_train)
            
            if(descriptors_query is not None):
                bf = cv2.BFMatcher(cv2.NORM_L1, crossCheck = False)
                matches = bf.match(descriptors_train, descriptors_query)
                matches = sorted(matches, key = lambda x : x.distance)
                matched_keys = len(matches)

                success = (100*matched_keys)/total_keys
            else:
                success = 0
        except:
            success = 0  
            print("orb error")      

        res = {
            "side": side,
            "success": success
        }
        outcome.append(res)

    return outcome    

def color(img, sides):

    image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    modified_image = image.reshape(image.shape[0]*image.shape[1], 3)

    number_of_colors = 7

    clf = KMeans(n_clusters = number_of_colors)
    labels = clf.fit_predict(modified_image)
    center_colors = clf.cluster_centers_

    label_count = [0 for i in range(number_of_colors)]

    for ele in labels:
        label_count[ele] += 1

    hsv_points = []

    for i in range(number_of_colors) :
        hsv_points.append((label_count[i]*100)/len(labels))

    hsv_colors = []
    
    for rgb in center_colors:
        hsv_colors.append(hsv(rgb))

    outcome = []

    for side in sides:
        success = 0.0
        for i in range(len(hsv_colors)):
            test_clr = hsv_colors[i]
            for train_clr in side['colors']:
                if(train_clr['lw'][0]<=test_clr[0] and train_clr['lw'][1]<=test_clr[1] and train_clr['lw'][2]<=test_clr[2] and train_clr['up'][0]>=test_clr[0] and train_clr['up'][1]>=test_clr[1] and train_clr['up'][2]>=test_clr[2]):
                    success += hsv_points[i]
                    break
        
        res = {
            "side": side['side'],
            "success": success
        }
        outcome.append(res)

    return outcome


# ./static/videos/output.avi
def getTarget(videos_path, videos_filename, target, caseID, client):

    # output = "./static/videos/{}/output.avi".format(caseID)

    for video in videos_filename:

        vid_path = videos_path + "/" + video

        vid_info = video.split(".")[0].split("_")

        vid_id = vid_info[0]
        vid_time = vid_info[1]
        vid_location = vid_info[2]

        vid_time = vid_time.split("-")

        vid_year = vid_time[0]
        vid_month = vid_time[1]
        vid_date = vid_time[2]
        vid_hour = vid_time[3]
        vid_min = vid_time[4]

        print(vid_id)
        print(vid_location)
        print(vid_year)
        print(vid_month)
        print(vid_date)
        print(vid_hour)
        print(vid_min)

        vid = cv2.VideoCapture(vid_path)

        width = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(vid.get(cv2.CAP_PROP_FPS))
        # codec = cv2.VideoWriter_fourcc(*'XVID')
        # out = cv2.VideoWriter(output, codec, fps, (width, height))
        print(width)
        print(height)
        print(fps)
        # fps = 0.0
        # count = 0

        # while True:
            _, img = vid.read()

            if img is None:
                print("Empty Frame")
                count+=1
                if count < 3:
                    continue
                else: 
                    break

            img_in = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) 
            img_in = tf.expand_dims(img_in, 0)
            img_in = transform_images(img_in, size)

            t1 = time.time()
            boxes, scores, classes, nums = yolo.predict(img_in)

            bags = []
            for i in range(nums[0]):
                temp_class = class_names[int(classes[0][i])]
                if (temp_class=="suitcase" or temp_class=="handbag" or temp_class=="backpack"):
                    box = []
                    [box.append(float(i)) for i in np.array(boxes[0][i])]
                    bag = {
                        "confidence": float(np.array(scores[0][i])),
                        "box": box
                    }
                    bags.append(bag) 
            
            # img = cv2.cvtColor(raw_img.numpy(), cv2.COLOR_RGB2BGR)
            h = img.shape[0]
            w = img.shape[1]

            if(not len(bags) > 0):
                out.write(img)
                continue

            bags_img = []

            for bag in bags:
                box = bag['box']
                cropped = img[int(box[1]*h):int(box[3]*h), int(box[0]*w):int(box[2]*w)]
                bags_img.append(cropped)    

            sides = []

            for s in target['sides']:
                sides.append(s['side'])

            bag_score = []   

            for bimg in bags_img:
                img_orb = orb_feature(bimg, sides, caseID)
                img_color = color(bimg, target['sides'])

                max_score = 0.0

                for j in range(len(sides)):
                    v1 = (img_orb[j]['success']*30)/100
                    v2 = (img_color[j]['success']*70)/100
                    if((v1+v2) > max_score):
                        max_score = v1+v2
                if(max_score < 40):
                    bag_score.append(-1)
                else:       
                    bag_score.append(max_score)

            best_bag_index = 0
            score = bag_score[0]

            for i in range(len(bag_score)):
                if(bag_score[i] > score):
                    score = bag_score[i]
                    best_bag_index = i
        
            if(not score == -1):
                best_bag_box = bags[best_bag_index]['box']
                img = draw_output(img, best_bag_box)


            fps  = ( fps + (1./(time.time()-t1)) ) / 2

            print("FPS: " + str(fps))
            out.write(img)
