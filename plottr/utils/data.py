import numpy as np
import pandas as pd


def interp_meshgrid_2d(xx, yy):
    """
    Try to find missing vertices in a 2d meshgrid,
    where xx and yy are the x and y coordinates of each point.
    This is just done by simple linear interpolation (using pandas).

    i.e.:
    if xx = [[0, 0], [1, nan]], yy = [[0, 1], [0, nan]]
    this will return [[0, 0], [1, 1]], [[0, 1], [0, 1]].
    """
    xx2 = pd.DataFrame(xx).interpolate(axis=1).values
    yy2 = pd.DataFrame(yy).interpolate(axis=0).values
    return xx2, yy2


def centers2edges_1d(arr):
    """
    Given an array of center coordinates, return the array of
    bounding vertices for the mesh that is defined by the coordinates.
    This is useful for methods like pcolor(mesh).

    To illustrate: if x are the centers, we return the inferred o's:

      o-x-o-x-o-x-o-x--o--x--o

    They are equidistantly spaced between the centers, such that the centers
    are in the middle between the vertices.
    """
    e = (arr[1:] + arr[:-1]) / 2.
    e = np.concatenate(([arr[0] - (e[0] - arr[0])], e))
    e = np.concatenate((e, [arr[-1] + (arr[-1] - e[-1])]))
    return e


def centers2edges_2d(centers):
    """
    Given a 2d array of coordinates, return the array of bounding vertices for
    the mesh that is defined by the coordinates.
    This is useful for methods like pcolor(mesh).
    Done by very simple linear interpolation.

    To illustrate: if x are the centers, we return the inferred o's:

    o   o   o   o
      x---x---x
    o | o | o | o
      x---x---x
    o   o   o   o
    """
    shp = centers.shape
    edges = np.zeros((shp[0]+1, shp[1]+1))

    # the central vertices are easy -- follow just from the means of the neighboring centers
    center = (centers[1:,1:] + centers[:-1,:-1] + centers[:-1,1:] + centers[1:,:-1])/4.
    edges[1:-1, 1:-1] = center

    # for the outer edges we just make the vertices such that the points are pretty much in the center
    # first average over neighbor centers to get the 'vertical' right
    _left = (centers[0,1:] + centers[0,:-1])/2.
    # then extrapolate to the left of the centers
    left = 2 * _left - center[0,:]
    edges[0, 1:-1] = left

    # and same for the other three sides
    _right = (centers[-1,1:] + centers[-1,:-1])/2.
    right = 2 * _right - center[-1,:]
    edges[-1, 1:-1] = right

    _top = (centers[1:,0] + centers[:-1,0])/2.
    top = 2 * _top - center[:,0]
    edges[1:-1, 0] = top

    _bottom = (centers[1:,-1] + centers[:-1,-1])/2.
    bottom = 2 * _bottom - center[:,-1]
    edges[1:-1, -1] = bottom

    # only thing remaining now is the corners of the grid.
    # this is a bit simplistic, but will be fine for now.
    # (mirror the vertex (1,1) of the diagonal at the outermost center)
    edges[0,0] = 2 * centers[0,0] - edges[1,1]
    edges[0,-1] = 2 * centers[0,-1] - edges[1,-2]
    edges[-1,0] = 2 * centers[-1,0] - edges[-2,1]
    edges[-1,-1] = 2 * centers[-1,-1] - edges[-2,-2]

    return edges
