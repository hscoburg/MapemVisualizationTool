import xml
import json
import xmltodict
import logging
import threading
import pymap3d as pm
import matplotlib.pyplot as plt
import random
import tkinter.filedialog as fd
import re

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
        
        self.selectedFiles = []
        self.mapems = []
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
        self.selectedFiles = []
        files = root.tk.splitlist(event.data)
        selectedFilenames = ""
        for file in files:
            fileStrVar = StringVar()
            fileStrVar.set(file)
            self.selectedFiles.append(fileStrVar)
            selectedFilenames = selectedFilenames + "\n" + file.split("/")[-1]
        self.displayText.set("selected file:" + selectedFilenames)
        self.warningMessage.set("")
        self.warningLabel.pack_forget()  
        
        self.mapems = self.GetFilesAsListsOfDicts(self.selectedFiles)   
    
    def Click(self, event):
        #self.filename.set(fd.askopenfilenames(parent= root, title='Choose a file', filetypes=[('MAPEM files', '*.xer;*.gser;*.json;*.xml')]))
        self.selectedFiles = []
        files = fd.askopenfilenames(parent= root, title='Choose a file', filetypes=[('MAPEM files', '*.xer;*.gser;*.json;*.xml')])
        fileNames = root.tk.splitlist(files)
        fileNamesString = ""
        for file in fileNames:
            fileStrVar = StringVar()
            fileStrVar.set(file)
            self.selectedFiles.append(fileStrVar) 
            fileNamesString =  fileNamesString + "\n" + file.split("/")[-1] 
            
        if  len(self.selectedFiles) > 0:               
            self.displayText.set("selected files:" + fileNamesString)
            self.warningMessage.set("")
            self.warningLabel.pack_forget()
            
            self.mapems = self.GetFilesAsListsOfDicts(self.selectedFiles)   
    
    def StartButton(self, printGraph, generateGPX):
        self.warningLabel.pack_forget()     
        self.messageLabel.pack_forget()
        
        if len(self.selectedFiles) == 0 :
            # no file given 
            self.warningMessage.set("please select a File here")
            self.warningLabel.pack()
            return
        self.VisualizeMapem(self.selectedFiles, printGraph.get(), generateGPX.get())
    #endregion
    
    def VisualizeMapem(self, filenames, printGraph, generateGpx):
        lanes = []
        connectionLanes = []
        refPoint = None
        intersectionDict = {"laneDict": {}, "connectionList": [], "RefPoint": {}} 
        for mapem in self.mapems:
            new_intersectionsDict = self.CalcualteLanesAbsoluteOffsetList(mapem)
            intersectionDict["laneDict"].update(new_intersectionsDict["laneDict"])
            intersectionDict["connectionList"].extend(new_intersectionsDict["connectionList"])
            intersectionDict["RefPoint"] = new_intersectionsDict["RefPoint"]
            (new_intersectionsDict)
            if intersectionDict == None:
                return
            
        lanes,connectionLanes,refPoint = self.getLaneCoordiates(intersectionDict)
            

        if generateGpx: 
            gpxThread = threading.Thread(target=self.generateGpxFile, args=(intersectionDict,), daemon= True)
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
    def getLaneCoordiates(self, intersectionDict):
        laneDict = intersectionDict["laneDict"]
        refPoint = intersectionDict["RefPoint"]
        connectionList = intersectionDict["connectionList"]
        
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
                    raise ValueError("No valid key found in lane dictionary")
                
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
        intersectionDict = {}
        
        if "MAPEM" not in mapem:
            self.warningMessage.set("No MAPEM found in file\nOnly .xer and .gser files are supported")
            self.warningLabel.pack()
            return 

        for xmlTag, intersection in mapem["MAPEM"]["map"]["intersections"].items(): 
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
                    
            intersectionDict.update( {"RefPoint": refPoint})
            intersectionDict.update( {"laneDict": laneDict})
            intersectionDict.update( {"connectionList" : connectionList})
        return intersectionDict
                
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
    
    """Validate if the given files are in the same sematic structur, MAPEM or PCAP Export, 
    and if they belong to the same Mapem given by name and framenumber, 
    if not block start button """
    def GivenFilesHandleSameMAPEM(self, dictList):
        #singleMapem
        if len(dictList) == 1:
            if "layerID" in dictList[0]["MAPEM"]["map"]:
                    return[False, "Single Mapem given where multiple are expected"]
            
            return [True]
        
        id = None
        maxLayers = int(dictList[0]["MAPEM"]["map"]["layerID"][0])
        listHandledLayerIds = []
        
        for dict in dictList:
            #check LayerIds
            if id == None:
                id = dict["MAPEM"]["map"]["intersections"]["IntersectionGeometry"]["id"]
            else:
                if id != dict["MAPEM"]["map"]["intersections"]["IntersectionGeometry"]["id"]:
                    return [False, "Intersection Id is different"]
                    
            currentLayerId = int(dict["MAPEM"]["map"]["layerID"]) - maxLayers * 10
            if currentLayerId > maxLayers:
                return [False, "LayerId not in range"]
            if currentLayerId not in listHandledLayerIds:
                listHandledLayerIds.append(currentLayerId)
            else:
                return [False, "LayerId not unique"]
        
        if len(listHandledLayerIds) != maxLayers:
            return [False, "not all layers of Mapem handled"]
                    
        return [True]
        
    #endregion
    
    #region GPX-File
    def generateGpxFile(self, intersection):
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

        gpxfilename  = ""
        for file in self.selectedFiles:
            gpxfilename =  gpxfilename + file.get().rsplit("/")[-1].rsplit(".", 1)[0] + "---"
        gpxfilename = gpxfilename[0:-3] + ".gpx"
        file = open(gpxfilename, "w")
        gpxString = tostring(rootGPX , encoding="utf8").decode("utf8")  #seperate decode, so its no binary string, write to file would fail otherwise
        
        file.write(gpxString)
        self.actionMessageString = self.actionMessageString + "Generated .gpx at: " + gpxfilename + "\n"
        self.actionMessage.set(self.actionMessageString)
        self.messageLabel.pack()
 
        logging.info("GPX generation Thread finishing")
    #endregion
    
    
    #region Parse Pcap File
    
    '''
    This method handles the dictionary given by a pcap export from wireshark.
    It usese the EtsiSubstring to identify the keys that need to be changed for the mapem bc. usually those keys start with "its-v2.".
    many elements have the suffix "_element" or "_tree" which are not needed for the mapem, so they will be removed.
    However, the "_tree" elements are duplicated by other elemnts, which have the same name, but just give the len of the following tree structure, those need to be overwritten.
    Furthermore lists have a different structure, the key of the listelements are "Item 0" counting upwards, the regualr expression cobnverts those into a list.    
    '''
    #def remove_substring_from_keys(self, data, etsiSubstring, fullyRemoveSubstring, overwriteSubstring):
    def remove_substring_from_keys(self, data, substring1, substring2, substring3):
        if isinstance(data, dict):
            new_dict = {}

            for key, value in data.items():
                # Nur Keys mit gewünschtem Prefix bearbeiten
                if substring1 not in key:
                    continue

                # Ist ein "_tree"-Key?
                if key.endswith(substring3):
                    base_key = key.replace(substring1, "").replace(substring3, "")
                    tree_dict = value

                    # Nur wenn Items vorhanden

                    if isinstance(tree_dict, dict) and "Item 0" in tree_dict:
                        first_item = tree_dict["Item 0"]
                        if isinstance(first_item, dict):
                            # Hole den ersten element-Key aus "Item 0"
                            element_key = next(iter(first_item))
                            element_type = element_key.replace(substring1, "").replace(substring2, "")
                            list_key = base_key

                            # Baue Liste aller "_element"-Einträge
                            elements = []
                            for item in tree_dict.values():
                                if isinstance(item, dict) and element_key in item:
                                    cleaned = self.remove_substring_from_keys(
                                        item[element_key],
                                        substring1, substring2, substring3
                                    )
                                    elements.append(cleaned)
                            if len(elements) == 1:
                                newDict2= {element_type:  elements[0]}
                            else:
                                newDict2 = {element_type: elements}
                            if type(new_dict[list_key]) is str:
                                new_dict[list_key] = []
                            new_dict[list_key] = (newDict2)
                    
                    elif isinstance(tree_dict, dict) and any(key.endswith("_tree") for key in tree_dict):
                        list_key = base_key
                        element_key =  next((key for key in tree_dict if key.endswith("_tree")), None)
                        element_type = element_key.replace(substring1, "").replace(substring2, "").replace(substring3, "")
                        
                        elements = []
                        new_dict3 = {}
                        for items in tree_dict.values():
                            if isinstance(items, dict) and "Item 0" in items:
                                for itemKey in list(items.keys()):
                                    
                                    cleaned = self.remove_substring_from_keys(
                                        items[itemKey],
                                        substring1, substring2, substring3
                                    )
                                    subElementKey = next(iter(cleaned)) 
                                    elements.append(list(cleaned.values())[0])
                        
                        
                        if len(elements) == 1:
                            new_dict3 = {subElementKey: elements[0]}
                        elif len(elements) > 1:
                            new_dict3 = { subElementKey: elements}
                        
                        newDict2 = {element_type: new_dict3}
                        if type(new_dict[list_key]) is str:
                            new_dict[list_key] = []
                        new_dict[list_key] = (newDict2)
                    
                    elif isinstance(tree_dict, dict) and any(key.endswith("_element") for key in tree_dict):
                        list_key = base_key
                        element_key =  next((key for key in tree_dict if key.endswith("_element")), None)
                        element_type = element_key.replace(substring1, "").replace(substring2, "").replace(substring3, "")
                        
                        elements = []
                        new_dict3 = {}
                        for items in tree_dict.values():
                            if isinstance(items, dict):
                                for itemKey in list(items.keys()):
                                    
                                    cleaned = self.remove_substring_from_keys(
                                        items[itemKey],
                                        substring1, substring2, substring3
                                    )
                                    new_dict3[itemKey.replace(substring1, "")] = cleaned
                        
                        newDict2 = {element_type: new_dict3}
                        if type(new_dict[list_key]) is str:
                            new_dict[list_key] = []
                        new_dict[list_key] = newDict2
                            
                        
                else:
                    cleaned_key = key.replace(substring1, "").replace(substring2, "").replace(substring3, "")
                    new_dict[cleaned_key] = self.remove_substring_from_keys(value, substring1, substring2, substring3)
                    
            return new_dict
        elif isinstance(data, list):
            return [self.remove_substring_from_keys(item, substring1, substring2, substring3) for item in data]
        else:
            return data
            
    
    def ParsePcapFileToMapemDict(self, pcapDict):
        mapemDictList = []
        itsVersion = next(iter(pcapDict[0]["_source"]["layers"]["etsiits"])).split(".")[0] + "."
        
        for frameFromPCAP in pcapDict:
            mapemElment = frameFromPCAP["_source"]["layers"]["etsiits"]
            
            mapemDict = self.remove_substring_from_keys(mapemElment, itsVersion, "_element", "_tree")
            
            mapemDictList.append(mapemDict)
        return mapemDictList
    
    def GetFilesAsListsOfDicts(self, filenameList):
        
        mapemDictList = []
        
        for filename in filenameList:
            mapemDict = None
            
            #parsing the file as mapem from json or xml, since we cant ensure the file ending to be correct (.xer.gser) we just try to parse and if it fails it fails.
            #TODO: maybe dont do it with exception handeling, but by the file given ...
            try:
                with open(filename.get(), 'r', encoding='utf-8') as file:
                    xmlStr = file.read()
                    mapemDict = xmltodict.parse(xmlStr) 
                            
            except xml.parsers.expat.ExpatError:  
                pass
            
            try: 
                file = open(filename.get())
                mapemDict = json.load(file)
                    
            except json.JSONDecodeError:
                pass
            
            try:
                if mapemDict[0]["_type"] == "pcap_file":
                    mapemDictList = self.ParsePcapFileToMapemDict(mapemDict)
            except KeyError:
                mapemDictList.append(mapemDict)
                pass
            
            
        givenMapemCheckResult = self.GivenFilesHandleSameMAPEM(mapemDictList)	
        if givenMapemCheckResult[0]:
            return mapemDictList
        self.warningLabel.pack()
        self.warningMessage.set(givenMapemCheckResult[1])
#endregion
        

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    MainApplication(root).pack(side="top", fill="both", expand=True)
    root.mainloop()