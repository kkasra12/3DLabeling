from dataclasses import dataclass
import numpy as np
import cv2 as cv


@dataclass
class KittiCalibrationData:
    P0: np.ndarray
    P1: np.ndarray
    P2: np.ndarray
    P3: np.ndarray
    R0_rect: np.ndarray
    Tr_velo_to_cam: np.ndarray
    Tr_imu_to_velo: np.ndarray



    

@dataclass
class Kitti3DLabelData:
    name: str
    truncated: float
    occluded: int
    alpha: float
    bbox: np.ndarray
    dimensions: np.ndarray
    location: np.ndarray
    rotation_y: float

    def __post_init__(self):

        self.h, self.w, self.l = self.dimensions

        c = np.cos(self.rotation_y)
        s = np.sin(self.rotation_y)

        # LiDAR coordinates
        # self.R = np.array([[c, -s, 0],
        #                    [s,  c, 0],
        #                    [0,  0, 1]])

        # self.t = self.location

        
        # Camera coordinates
        self.R = np.array([[ c,  0, s],
                           [ 0,  1, 0],
                           [-s,  0, c]])

        # since vehicle coordiante is
        # x: pointing forward (towards front of the vehicle)
        # y: pointing left
        # z: pointing up
        self.R = self.R @ np.array([[1, 0, 0],
                                    [0, 0, -1],
                                    [0, 1, 0]])

        

        self.t = self.location.reshape((-1,1))

        self.Rt = np.hstack((self.R,self.t))



@dataclass
class Cuboid:
    points: np.ndarray
    



def get_3D_cuboid_graph(label):
    "creates 3D cuboid points in the camera coordiante system and their graph"
    w,h,l = label.w, label.h, label.l

    # x_corners = [l/2, l/2, -l/2, -l/2, l/2, l/2, -l/2, -l/2];
    # y_corners = [0,0,0,0,-h,-h,-h,-h];
    # z_corners = [w/2, -w/2, -w/2, w/2, w/2, -w/2, -w/2, w/2];
    
    
    x_coords = np.array([ l/2,  l/2, -l/2, -l/2,  l/2,  l/2, -l/2, -l/2])
    y_coords = np.array([ w/2, -w/2,  w/2, -w/2,  w/2, -w/2,  w/2, -w/2])
    z_coords = np.array([   0,    0,   0,    0,   h,    h,      h,    h])

    points = np.vstack((x_coords, y_coords, z_coords))
    points = label.R @ points + label.t

    
    edges = np.array([[0,1],
                      [0,2],
                      [1,3],
                      [2,3],
                      [0,4],
                      [1,5],
                      [2,6],
                      [3,7],
                      [4,5],
                      [4,6],
                      [5,7],
                      [6,7]])

    return points, edges
                      
    

def find_vehicle_to_camera_pose(calib_data, label):
    """returns the calibration matrix and the relative
    rotation+translation taking a 3D point from the vehicle coordinate
    systems to the camera (P2) coordiate system
    """
    P = calib_data.P2
    K = P[:,:3]
    R = label.R
    t = label.t + np.reshape(np.linalg.inv(K) @ P[:,3], (-1,1))

    return K,R,t

    
    
    
        

def draw_3d_labels(I, calib_data, label_data):
    "Draw 3D bounding boxes on image"

    for label in label_data:
        points, edges = get_3D_cuboid_graph(label)

        
        K,R,t = find_vehicle_to_camera_pose(calib_data, label)
        P = K @ np.hstack((R, t))
        points2d = P @ np.vstack((points, np.ones((1, 8))))
        points2d = points2d[:2] / points2d[[2]]
        points2d = points2d.T

        radius = 4
        color = (255, 0, 0)
        thickness = -2
        for p in points2d:
            
            I = cv.circle(I, p.astype(np.int64), radius, color, thickness)
            
        
        color = (0, 0, 255)
        thickness = 1

        for i,j in edges:
            pi = points2d[i].astype(np.int64)
            pj = points2d[j].astype(np.int64)

            cv.line(I, pi, pj, color, thickness)
            
            

        

    
    

    

def read_3d_label_file(label_file):
    """
    read the label files:

    from devkit_object/readme.txt:

    1 type         Describes the type of object: 'Car', 'Van', 'Truck',
                     'Pedestrian', 'Person_sitting', 'Cyclist', 'Tram',
                     'Misc' or 'DontCare'
    1    truncated    Float from 0 (non-truncated) to 1 (truncated), where
                     truncated refers to the object leaving image boundaries
    1    occluded     Integer (0,1,2,3) indicating occlusion state:
                     0 = fully visible, 1 = partly occluded
                     2 = largely occluded, 3 = unknown
    1    alpha        Observation angle of object, ranging [-pi..pi]
    4    bbox         2D bounding box of object in the image (0-based index):
                     contains left, top, right, bottom pixel coordinates
    3    dimensions   3D object dimensions: height, width, length (in meters)
    3    location     3D object location x,y,z in camera coordinates (in meters)
    1    rotation_y   Rotation ry around Y-axis in camera coordinates [-pi..pi]
    1    score     
    
    """

    object_list = []
    with open(label_file) as f:
        
        
        for line in f:
            split_list = line.split()

            if split_list == []:
                continue

            name = split_list[0]
            truncated = float(split_list[1])
            occluded = int(split_list[2])
            alpha = float(split_list[3])
            bbox = np.array(split_list[4:8], dtype=np.float64)
            dimensions = np.array(split_list[8:11], dtype=np.float64)
            location = np.array(split_list[11:14], dtype=np.float64)
            rotation_y = float(split_list[14])
            
            object_list.append(Kitti3DLabelData(name, truncated,
                                                occluded,
                                                alpha, 
                                                bbox,
                                                dimensions,
                                                location,
                                                rotation_y))


            
    return object_list
            
            



def read_calib_file(calib_file):
    "reads the calibration data from file"

    data_dic = {}
    
    with open(calib_file) as f:
        for line in f:
            split_list = line.split()

            if split_list == []:
                continue
            

            key = split_list[0][:-1]
            value = np.array(split_list[1:], dtype='float64').reshape((3,-1))

            data_dic[key] = value


    return KittiCalibrationData(**data_dic)




            
                  

            


    
        
