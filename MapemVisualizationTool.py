import xml
import json
import xmltodict
import logging
import threading
import pymap3d as pm
import matplotlib.pyplot as plt
import random

from tkinter.filedialog import askopenfilename
from tkinterdnd2 import DND_FILES, TkinterDnD
from tkinter import StringVar, BooleanVar, LabelFrame, Label, Checkbutton, Button, Frame
from xml.etree.ElementTree import Element, SubElement, tostring

class MainApplication(Frame):
    
    actionMessageString = ""
    _lonLatFloatAccuracy = 10000000
    _meterToCentimeter = 100
    
    #region GUI
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        
        self.filename = StringVar()
        self.actionMessage = StringVar()
        self.warningMessage = StringVar()
        printGraph = BooleanVar()
        generateGPX = BooleanVar()
        self.displayText = StringVar(value = "Drag and Drop single MAPEM message exported as json from wireshark here")

        dragDropFrame = LabelFrame(root, padx=5, pady=5)
        self.warningLabel =  Label(dragDropFrame, textvar = self.warningMessage, bg ="red")
        self.messageLabel =  Label(dragDropFrame, textvar = self.actionMessage, bg ="green")
        infoLabel =  Label(dragDropFrame, textvar = self.displayText)
        infoLabel.pack()
        
        root.geometry("500x200")
        root.title("Simple MAPEM-Visualizer") 
        

        infoLabel.bind ("<Button-1>", self.Click)
        dragDropFrame.drop_target_register(DND_FILES)
        dragDropFrame.dnd_bind('<<Drop>>',self.drop)
        dragDropFrame.pack(padx=10, pady=10)

        
        graphCheck = Checkbutton(root, text="print Graph", variable = printGraph)
        gpxCheck = Checkbutton(root, text="generate GPX", variable = generateGPX)
        graphCheck.pack()
        gpxCheck.pack()

        startButton = Button(root, text="Start", command= lambda: self.StartButton(printGraph, generateGPX))
        startButton.pack()
    
    def drop(self, event):
        if (event.data[0] =='{'):
            event.data = event.data[1:len(event.data)-1]
        self.filename.set(event.data)
        self.displayText.set("selected file: \n" + event.data)
        self.warningMessage.set("")
        self.warningLabel.pack_forget()  
    
    def Click(self, event):
        self.filename.set(askopenfilename())
        if  self.filename.get()!="":
            self.displayText.set("selected file: \n" + self.filename.get())
            self.warningMessage.set("")
            self.warningLabel.pack_forget()   
    
    def StartButton(self, printGraph, generateGPX):
        self.warningLabel.pack_forget()     
        self.messageLabel.pack_forget()
        
        if self.filename.get()== self.filename._default:
            # no file given 
            self.warningMessage.set("please select a File here")
            self.warningLabel.pack()
            return
        self.VisualizeMapem(self.filename.get(), printGraph.get(), generateGPX.get())
    #endregion
    
    def VisualizeMapem(self, filename, printGraph, generateGpx):
        fileAsDict = self.GetFileAsDict(filename)
        intersectionsDict = self.CalcualteLanesAbsoluteOffsetList(fileAsDict)
        if intersectionsDict == None:
            return
        
        lanes, connectionLanes, refPoint = self.getLaneCoordiates(intersectionsDict)
        
        if generateGpx: 
            gpxThread = threading.Thread(target=self.generateGpxFile, args=(intersectionsDict,), daemon= True)
            gpxThread.start()
        
        if printGraph:
            # mathplot is not threadsave, so just run it in the main thread if required
            self.printGraph(lanes, connectionLanes, refPoint)    
        return
    
    #region PyPlot
    def printGraph(self, lanes, connectionLanes, refPoint):
        for lane in lanes:
            plt.plot(lane["x_vals"], lane["y_vals"], marker= lane["marker"], linestyle= lane["linestyle"], color = lane["color"], label = lane["label"] )
        for connectionLane in connectionLanes:
            plt.plot(connectionLane["x_vals"], connectionLane["y_vals"], linestyle= connectionLane["linestyle"], color = connectionLane["color"], label = connectionLane["label"] )
        plt.legend()
        plt.scatter(refPoint["long"], refPoint["lat"], color = "red", s = 200, label= "Refference Point")
        plt.show( )
        self.actionMessageString = self.actionMessageString + "Plotted MAPEM\n"
        self.actionMessage.set(self.actionMessageString)
        self.messageLabel.pack()

    #endregion
    
    #region Calculations
    def getLaneCoordiates(self, intersectionsDict):
        intersection = None
        for mapem in intersectionsDict.values():
            intersection = mapem
            #TODO: Fill with life!
            
        laneDict = intersection["laneDict"]
        refPoint = intersection["RefPoint"]
        connectionList = intersection["connectionList"]
        
        lanes = []
        
        for laneId, lane in laneDict.items():
            r = lambda: random.randint(0,255)
            red = r()
            green = r()
            yellow = r()
            lanecolor = '#{:02x}{:02x}{:02x}'.format( int((red * 0.60)), int(green * 0.60), int(yellow * 0.60))
            lineLabel= "LaneId:  " + laneId
            if "xAbsolute" in lane[0]:
                x_values = [point["xAbsolute"] for point in lane]
                y_values = [point["yAbsolute"] for point in lane]  
            lanes.append({"x_vals": x_values, "y_vals":y_values, "marker":'o', "linestyle" : '-', "color" : lanecolor, "label" : lineLabel})
        
        connectionLanes = [] 
        for connection in connectionList:
            xConnectionList = []  
            yConnectionList = []

            for lane in laneDict.values():
                if "xAbsolute" in lane[0]:
                    keywordX= "xAbsolute"
                    keywordY= "yAbsolute"
                    multiplicator = 1
                elif "Lon" in lane[0]:
                    keywordX= "Lon"
                    keywordY= "Lat"
                    multiplicator = 10000000
                else:
                    print("not suPPORTED ") #TODO throw error
                    
                if lane[0]["laneId"] == connection[0]: #startPoint
                    if xConnectionList == []:
                        xConnectionList.append(lane[0][keywordX]/multiplicator)
                        yConnectionList.append(lane[0][keywordY]/multiplicator)
                    else:   #replace startPoint, needed, when endpoint /// happens, when destination lane has an lower id than start lane, since the loop iterates over all lanes. 
                        xConnectionList[0] = lane[0][keywordX]/multiplicator
                        yConnectionList[0] = lane[0][keywordY]/multiplicator

                if lane[0]["laneId"] == connection[1]: #endPoint
                    if xConnectionList == []:   #startpoint (xConnectionList[0]) will be replaced when startlane is reached in loop
                        xConnectionList.append(lane[0][keywordX]/multiplicator)
                        yConnectionList.append(lane[0][keywordY]/multiplicator)

                    xConnectionList.append(lane[0][keywordX]/multiplicator)
                    yConnectionList.append(lane[0][keywordY]/multiplicator)

            label = "Connection: " + str(connection[0]) + " to " + str(connection[1])
            connectionLanes.append({"x_vals": xConnectionList, "y_vals": yConnectionList, "linestyle": '--', "color" : "black", "label" : label})

        return lanes, connectionLanes, refPoint
    
    def CalcualteLanesAbsoluteOffsetList(self, mapem):
        intersectionsDict = {}
        
        if "MAPEM" not in mapem:
            self.warningMessage.set("No MAPEM found in file\nOnly .xer and .gser files are supported")
            self.warningLabel.pack()
            return 

        for xmlTag, intersection in mapem["MAPEM"]["map"]["intersections"].items(): 
            name = intersection["name"]
            laneDict = {}
            intersection["refPoint"]["lat"] = int(intersection["refPoint"]["lat"])/self._lonLatFloatAccuracy
            intersection["refPoint"]["long"] = int(intersection["refPoint"]["long"])/self._lonLatFloatAccuracy
            refPoint = intersection["refPoint"]
            connectionList = [] # [0] = start, [1] = destination; biodirctional connections need to be duplicated in the list 
            
            for laneNodeList in intersection["laneSet"]["GenericLane"]:
                nodeList = []
                connectionTree = []
                
                firstPoint = True
                yAbsolute, xAbsolute = 0, 0
                
                for node in laneNodeList["nodeList"]["nodes"]["NodeXY"]:
                    NodeOffsetPointXY = node["delta"]
                    
                    if "lon" in list(NodeOffsetPointXY.values())[0]: 
                        xAbsolute, yAbsolute = self.XYOffsetCalc(refPoint, NodeOffsetPointXY["node-LatLon"]["lon"], NodeOffsetPointXY["node-LatLon"]["lat"])
                        Lon = int(NodeOffsetPointXY["node-LatLon"]["lon"])
                        Lat = int(NodeOffsetPointXY["node-LatLon"]["lat"])
                    
                    else: 
                        xAbsolute = xAbsolute + int(list(NodeOffsetPointXY.values())[0]["x"])
                        yAbsolute = yAbsolute + int(list(NodeOffsetPointXY.values())[0]["y"])
                        Lat, Lon = self.LongLatCalc(refPoint, xAbsolute, yAbsolute )
                    
                    node = {
                        "Lon": Lon,
                        "Lat": Lat, 
                        "xAbsolute": xAbsolute,
                        "yAbsolute": yAbsolute 
                    }
                    
                    if firstPoint: 
                        firstPoint = False
                        node["laneId"] = int(laneNodeList["laneID"])
                    
                    nodeList.append(node)
                laneDict.update({str(nodeList[0]["laneId"]): nodeList})       
                
                connectionTree = []
                if "connectsTo" in laneNodeList: 
                    if type(laneNodeList["connectsTo"]["Connection"]) is list:
                        connectionTree = laneNodeList["connectsTo"]["Connection"]   
                    else:
                        connectionTree.append(laneNodeList["connectsTo"]["Connection"])
                
                for connection in connectionTree:
                    startPoint = int(laneNodeList["laneID"])
                    endPoint = int(connection["connectingLane"]["lane"])
                    signalGroup = None
                    if "signalGroup" in connection:
                        signalGroup = int(connection["signalGroup"])
                        
                    connectItem = [ startPoint , endPoint, signalGroup]    
                    connectionList.append(connectItem)
            intersectionsDict.update({name : {"RefPoint": refPoint,
                                              "laneDict": laneDict,
                                              "connectionList" : connectionList
                                              }
                                      })
        return intersectionsDict
                
    def LongLatCalc(self, refPoint, xCentimeters, yCentimeters):
        xMeters = xCentimeters / self._meterToCentimeter
        yMeters = yCentimeters / self._meterToCentimeter
        latRefference = float(refPoint["lat"])
        longRefference = float(refPoint["long"])
        new_latitude, new_longitude, height = pm.enu2geodetic(xMeters, yMeters, 0 , latRefference, longRefference, 0 )
        return new_latitude, new_longitude
        
    def XYOffsetCalc(self, refPoint, lon, lat):
        x,y,h =pm.geodetic2enu(lat = float(refPoint["lat"])/self._lonLatFloatAccuracy,
                               lon = float(refPoint["long"])/self._lonLatFloatAccuracy,
                               h = 0,
                               lon0 = float(lon)/self._lonLatFloatAccuracy,
                               lat0= float(lat)/self._lonLatFloatAccuracy,
                               h0 = 0
                               )
        return x/self._meterToCentimeter ,y/self._meterToCentimeter #working with centimeters 
    #endregion
    
    #region GPX-File
    def generateGpxFile(self, intersectionsDict):
        intersection = None
        for mapem in intersectionsDict.values():
            intersection = mapem
            #TODO: Fill with life!
            
        laneDict = intersection["laneDict"]
        refPoint = intersection["RefPoint"]
        connectionList = intersection["connectionList"]
        logging.info("GPX generation Thread starting")
        rootGPX = Element("gpx")
        
        for lane in laneDict.values():
            r = lambda: random.randint(0,255)
            red = r()
            green = r()
            yellow = r()
            nodecolor = '#{:02x}{:02x}{:02x}'.format(red, green, yellow)
            lineLabel= "LaneId:  " + str(lane[0]["laneId"])
            
            routeGpxElement  = SubElement(rootGPX, "trk")
            colorGpxElement = SubElement(routeGpxElement, "extensions")
            colorGPXElement2 = SubElement(colorGpxElement, "line", {"xmlns":"http://www.topografix.com/GPX/gpx_style/0/2" })
            colorGPXElement3 = SubElement(colorGPXElement2, "color")
            colorGPXElement3.text = nodecolor

            routeName = SubElement(routeGpxElement, "name")
            routeName.text = lineLabel
            routeGPXsegment = SubElement(routeGpxElement, "trkseg")

            routeGpxElement.text = routeName
            
            for node in lane:
                routeWaypoint = SubElement(routeGPXsegment, "trkpt")
                routeWaypoint.set("lat", str(node["Lat"]))
                routeWaypoint.set("lon", str(node["Lon"]))
        
        for connection in connectionList:
            routeName= "SignalGroup: " + str(connection[2])
            routeGpxElement  = SubElement(rootGPX, "trk")
            colorGpxElement = SubElement(routeGpxElement, "extensions")
            colorGPXElement2 = SubElement(colorGpxElement, "line", {"xmlns" :"http://www.topografix.com/GPX/gpx_style/0/2" })
            colorGPXElement3 = SubElement(colorGPXElement2, "color")
            colorGPXElement3.text = "000000"
            routeGpxElementName = SubElement(routeGpxElement, "name") 
            routeGpxElementName.text = routeName


            #connection startpoint
            routeGPXsegment= SubElement(routeGpxElement, "trkseg")
            connectionStartWaypoint = SubElement(routeGPXsegment, "trkpt")
            connectionStartWaypoint.set("lat", str(laneDict[str(connection[0])][0]["Lat"])) #first Element of connection is startPoint
            connectionStartWaypoint.set("lon", str(laneDict[str(connection[0])][0]["Lon"]))
            connectionStartWaypointName  = SubElement(connectionStartWaypoint, "name")
            connectionStartWaypointName.text = "Start of lane-connetion "

            #connection destination
            connectionEndWaypoint = SubElement(routeGPXsegment, "trkpt")
            connectionEndWaypoint.set("lat", str(laneDict[str(connection[1])][0]["Lat"])) #second Element of connection is endPoint
            connectionEndWaypoint.set("lon", str(laneDict[str(connection[1])][0]["Lon"]))
            connectionEndWaypointName  = SubElement(connectionEndWaypoint, "name")
            connectionEndWaypointName.text = "End of lane-connetion"
        
        refPointGPX = SubElement(rootGPX, "wpt")
        refPointGPX.set("lat", str(refPoint["lat"]))
        refPointGPX.set("lon", str( refPoint["long"]))
        nameRefPointGPX = SubElement(refPointGPX, "name")
        nameRefPointGPX.text = "Refferencepoint"
        symbolFlagRefPoint = SubElement(refPointGPX, "sym")
        symbolFlagRefPoint.text = "flag, red" #idk if this works :D ///should identify the symbol used by gpx client software, but doesnt seem to be unified

        gpxfilename  = self.filename.get().rsplit(".", 1)[0] + ".gpx"
        file = open(gpxfilename, "w")
        gpxString = tostring(rootGPX , encoding="utf8").decode("utf8")  #seperate decode, so its no binary string, write to file would fail otherwise
        
        file.write(gpxString)
        self.actionMessageString = self.actionMessageString + "Generated .gpx at: " + gpxfilename + "\n"
        self.actionMessage.set(self.actionMessageString)
        self.messageLabel.pack()
 
        logging.info("GPX generation Thread finishing")
    #endregion
    #region Parse File
    def GetFileAsDict(self, filename):
        dict = None
        
        #parsing the file as mapem from json or xml, since we cant ensure the file ending to be correct (.xer.gser) we just try to parse and if it fails it fails.
        #TODO: maybe dont do it with exception handeling, but by the file given ...
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                xmlStr = file.read()
                dict = xmltodict.parse(xmlStr) 
                        
        except xml.parsers.expat.ExpatError:  
            pass
        
        try: 
            file = open(filename)
            dict = json.load(file)
                   
        except json.JSONDecodeError:
            pass
        
        #TODO: handle pcap exports!!!
        
        return dict
#endregion
        

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    MainApplication(root).pack(side="top", fill="both", expand=True)
    root.mainloop()