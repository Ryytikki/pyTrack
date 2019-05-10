# import the necessary packages
from imutils.video import VideoStream
import argparse
import datetime
#import imutils
import time
import numpy as np
import cv2
#import sys
#from astropy.stats.circstats import circmean
import matplotlib.pyplot as plt

from videocaptureasync import VideoCaptureAsync
from scipy.spatial import distance

class Participant():
    def __init__(self, xrange, yrange):
        self.xRange = xrange
        self.yRange = yrange
        
        self.X = 0
        self.Y = 0
        
        self.XYmag = []
        self.XYang = []
        
        self.flow = []

class OptFlow():
    def __init__(self):
        # Some more parameters.
        self.REL_PHASE_FEEDBACK = 0
        self.ANY_FEEDBACK = 1
        self.MOVT_PLOTTING = 1
        self.feedback_circle_r = 200 # The size of the circle in the center of the screen.
        self.mag_threshold = .1 # This is important. We try to reduce noise by zero-ing out fluctuations in pixel intensity below a certain threshold.
        self.ABS_FRAME_DIFF = []
        self.FAKE_FRAME_COUNTER = 0
        
        self.participents = []
         
        self.finished = False
        self.recording = False
        
        # construct the argument parser and parse the arguments
        ap = argparse.ArgumentParser()
        ap.add_argument("-v", "--video", help="path to the video file")
        ap.add_argument("-a", "--min-area", type=int, default=500, help="minimum area size")
        self.args = vars(ap.parse_args())
        
        # if the video argument is None, then we are reading from webcam
        if self.args.get("video", None) is None:
            self.vs = VideoCaptureAsync(src=0).start()
        # otherwise, we are reading from a video file
        else:
            self.vs = cv2.VideoCaptureAsync(self.args["video"])
        
        self.frame00 = self.vs.read()[1]
        self.frame0 = cv2.flip(cv2.cvtColor(self.frame00,cv2.COLOR_BGR2GRAY),1)
        self.frame1 = []
        self.frame01 = []
        self.hsv = np.zeros_like(self.frame00)
        self.hsv[..., 1] = 255
        
        s = np.shape(self.frame0)
        print("Your video frame size is %d by %d." % s)
        self.of_fb_winsize = np.mean(np.divide(s,30),dtype='int')
        self.center=(np.int(np.round(s[1]/2)),np.int(np.round(s[0]/2)))
        
        part = Participant(range(0,np.int(np.round(s[1]/2))), range(0, s[0]))
        self.participents.append(part)
        part = Participant((range(np.int(np.round(s[1]/2)),s[1]-1)), (range(0, s[0])))
        self.participents.append(part)
        
        self.TIME = [time.time()]
        
        
    def update(self):
    
        # Check if streaming has finished
        if self.finished:
            return
        
        self.frame01 = self.vs.read()[1]
        self.frame1 = cv2.flip(cv2.cvtColor(self.frame01,cv2.COLOR_BGR2GRAY),1)
        
        # Don't process identical frames, which could happen if the camera is covertly upsampling.
        # Somehow, by coincidence, the fps with flow estimation is just about the 
        # real fps without flow estimation but with skipping identical frames (fake new frames).
        if self.recording:
            frameDiff = np.sum(np.abs(frame01 - frame00))
            ABS_FRAME_DIFF.append(frameDiff)
            if frameDiff == 0:
                FAKE_FRAME_COUNTER += 1
                if FAKE_FRAME_COUNTER == 100:
                    np.mod(FAKE_FRAME_COUNTER)
                    print("100 fake frames")
                return
 
        # https://docs.opencv.org/4.0.1/dc/d6b/group__video__track.html#ga5d10ebbd59fe09c5f650289ec0ece5af
        # (..., ..., ...,                                  pyr_scale, levels, winsize, iterations, poly_n, poly_sigma, flags	)
        # pyr_scale = .5 means each next layer is .5 the size of the previous.
        # levels, number of layers
        # winsize, larger is smoother and faster but lower res
        # iterations, ...
        # poly_n, typically 5 or 7
        # poly_sigma, 1.1 or 1.5
        # flags, extra options
        flow = cv2.calcOpticalFlowFarneback(self.frame0, self.frame1, None, .5, 0, self.of_fb_winsize, 1, 3, 1.1, 0)
        
        # average angle
        mag, ang = cv2.cartToPolar(flow[...,0], flow[...,1])
        
        self.hsv[...,0] = ang*180/np.pi/2
        self.hsv[...,2] = mag
        
        self.TIME.append(time.time() - self.TIME[0])
        
        # Find the mean vector.
        # Why was this NAN? this caused a lot of bugs with the code if the entire
        # array was below the threshold amount
        flow[mag<self.mag_threshold,0]=0#np.NaN
        flow[mag<self.mag_threshold,1]=0#np.NaN
        
        # Work out the x/y and mag/angle components of each participant
        for item in self.participents:
            item.X = np.nanmean(flow[:, item.xRange, 0])
            item.Y = np.nanmean(flow[:, item.xRange, 1])
            item.XYmag.append(np.sqrt(item.X ** 2 + item.Y ** 2))
            item.XYang.append(np.arctan2(item.Y, item.X))
            if item.XYang[-1] < 0:
                item.XYang[-1] = np.mod(item.XYang[-1], np.pi) + np.pi
        
        if len(self.participents) >= 2:
            # Get the relative angle between the first two participents
            relAng = np.mod(np.subtract(self.participents[0].XYang[-1],self.participents[1].XYang[-1]), 2*np.pi)
            xrel, yrel = cv2.polarToCart(1, relAng)
        else:
            xrel, yrel = 0, 0
        
        # # Experiment with the scaling and thresholding to map motion b/w 0 and 255.
        mag[mag<self.mag_threshold]=0
        mag=mag*10
        if np.max(np.abs(mag))>255:
            print(np.max(np.abs(mag)))
            
        self.hsv[...,2] = mag 
        # I don't remember any more why I commented this out. Oh yeah. You want to be able to tell how much movement is detected, and how fast, from the video.
        # hsv[...,2] = cv2.normalize(mag,None,alpha=0,beta=255,norm_type=cv2.NORM_MINMAX)
        bgr = cv2.cvtColor(self.hsv,cv2.COLOR_HSV2BGR)
        
        cv2.putText(bgr, datetime.datetime.now().strftime("%A %d %B %Y %I:%M:%S%p"),
                (10, bgr.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
        
        cv2.circle(bgr, self.center, self.feedback_circle_r, (25,25,25,1), thickness = 1)
        
        camImg = self.frame01.copy()
        for i, item in enumerate(self.participents):
            cv2.rectangle(camImg, (item.xRange[0], item.yRange[0]), (item.xRange[-1], item.yRange[-1]), (255,i * 255,(1-i)*255,1), thickness = 2)
        
        # Either display individual velocity vectors or the relative phase.
        if self.REL_PHASE_FEEDBACK == 1:
            cv2.line(bgr, self.center, (int(self.center[0] + xrel[0] * self.feedback_circle_r),int(self.center[1] + yrel[0] * self.feedback_circle_r)), (200,200,250,1), thickness = 2)
        else:
            cv2.line(bgr, self.center, (int(self.center[0] + self.participents[0].X * self.feedback_circle_r),int(self.center[1] + self.participents[0].Y * self.feedback_circle_r)), (255,0,255,1), thickness = 2)
            cv2.line(bgr, self.center, (int(self.center[0] + self.participents[1].X * self.feedback_circle_r),int(self.center[1] + self.participents[1].Y * self.feedback_circle_r)), (255,255,0,1), thickness = 2)
        
        if self.ANY_FEEDBACK:
            cv2.imshow("Camera", camImg)
            cv2.imshow('Dense optic flow',bgr)
    
        self.frame0 = self.frame1
        self.frame00 = self.frame01
        
    def closeStream(self):
        self.vs.stop() if self.args.get("video", None) is None else self.vs.release()
        cv2.destroyAllWindows()
        self.TIME = self.TIME[1:]   
        self.TIME = [t - self.TIME[0] for t in self.TIME]
        
        self.finished = True
        
        if self.MOVT_PLOTTING:
            self.runVis()
        
    def runVis(self):
        plt.subplot(311)
        DTIME = np.diff(self.TIME)
        SR = np.divide(1,DTIME) 
        plt.xlabel('Time, s')
        plt.ylabel('Frame acquisition rate, fps')
        plt.plot(self.TIME[1:],SR,'-')   

        plt.subplot(312)
        plt.xlabel('Time [s]')
        plt.ylabel('|X| [px]')
        for item in self.participents:
            plt.plot(self.TIME,item.XYmag,'-')

        plt.subplot(313)
        plt.xlabel('Time [s]')
        plt.ylabel(r"$ \bar \phi $ [rad]")
        for item in self.participents:
            plt.plot(self.TIME,item.XYang,'-')
        plt.ylim(0*np.pi,2*np.pi)
        plt.yticks((0,.5*np.pi,np.pi,1.5*np.pi,2*np.pi))
        
        plt.show()