import numpy as np
from lxml import etree as ET


def fix_bounding_box(element: ET.Element, xt: float, yt: float, scaling_factor: float = None):
    bounding_box = np.asarray([float(x) for x in element.attrib['BoundingBox'].split(" ")])
    translation = np.array([xt, yt, xt, yt])

    if scaling_factor is None:
        final_coords = bounding_box + translation
    else:
        scaled_coords = bounding_box * scaling_factor
        final_coords = scaled_coords + translation

    final_coords = np.round(final_coords, 2)

    element.attrib['BoundingBox'] = f"{final_coords[0]} {final_coords[1]} {final_coords[2]} {final_coords[3]}"


def get_element_center(element: ET.Element) -> np.ndarray:
    bb = element.attrib['BoundingBox']
    bounding_box = [float(x) for x in bb.split(" ")]
    coords = np.asarray([[bounding_box[0], bounding_box[1]], [bounding_box[2], bounding_box[3]]])
    x_center, y_center = get_center(coords)
    return np.array([x_center, y_center])


def get_translation_vector(point_a: np.ndarray, point_b: np.ndarray) -> float:
    vect = []
    for i in range(len(point_a)):
        dist = point_a[i] - point_b[i]
        vect.append(dist)
    return np.array(vect)


def get_center(all_coords: np.ndarray) -> tuple:
    """Gets the center (x,y coordinates) of an element, usually a fragment

    Parameters:
    all_coords (numpy): coordinates of all nodes(atoms) of the fragment

    Returns:
    tuple: (x,y) center point of fragment

   """

    max_x, max_y = all_coords.max(axis=0)
    min_x, min_y = all_coords.min(axis=0)

    x_center = (min_x + max_x) / 2
    y_center = (min_y + max_y) / 2

    return x_center, y_center


def get_translation(old_coords, new_coords):
    """
    Gets the x and y translation needed to scale the fragment and translate it back to the previous center

    Parameters:
    all_coords (numpy): coordinates of all nodes(atoms) of the fragment
    scaled_coords(numpy): coordinates of all nodes(atoms) of the fragment after scaling

    Returns:
    tuple: x and y amount to translate
    """

    x_center, y_center = get_center(old_coords)
    scaled_x_center, scaled_y_center = get_center(new_coords)

    x_translate = x_center - scaled_x_center
    y_translate = y_center - scaled_y_center

    return x_translate, y_translate


def translate(coords, x_translate, y_translate):
    """Translates the input coordinates by the given x and y translation amount

    Parameters:
    coords (numpy): coordinates of all elements to translate
    x_translate: amount to translate on x-axis
    y_translate: amount to translate on y-axis


    Returns:
    numpy: array of translated coordinates

   """
    translation = np.array([x_translate, y_translate])
    final_coords = coords + translation
    return final_coords


def get_distance(point_a: np.ndarray, point_b: np.ndarray):
    # This works because the Euclidean distance is the l2 norm, and the default value of the ord parameter in
    # numpy.linalg.norm is 2.
    dist = np.linalg.norm(point_a - point_b)
    return dist
