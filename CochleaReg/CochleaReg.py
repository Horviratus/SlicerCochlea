#======================================================================================
#  3D Slicer [1] plugin that uses elastix toolbox [2] Plugin for Automatic Cochlea    #
#  Image Registration (ACIR) [3]. More info can be found at [4]                       #
#  Sample cochlea datasets can be downloaded using Slicer Datastore module            #
#                                                                                     #
#  Contributers:                                                                      #
#      - Christopher L. Guy,   guycl@vcu.edu              : Original source code.     #
#      - Ibraheem Al-Dhamari,  idhamari@uni-koblenz.de    : Plugin design.            #
#      - Michel Peltriaux,     mpeltriaux@uni-koblenz.de  : Programming & testing.    #
#      - Anna Gessler,         agessler@uni-koblenz.de    : Programming & testing.    #
#      - Jasper Grimmig        jgrimmig@uni-koblenz.de    : Programming & testing.    #
#      - Pepe Eulzer           eulzer@uni-koblenz.de      : Programming & testing.    #
#  [1] https://www.slicer.org                                                         #
#  [2] http://elastix.isi.uu.nl                                                       #
#  [3] Al-Dhamari et al., (2017): ACIR: automatic cochlea image registration.         #
#      In: Proceedings SPIE Medical Imaging 2017: Image Processing;. SPIE. Bd.        #
#          10133. S. 10133p1-10133p5                                                  #
#  [4] https://mtixnat.uni-koblenz.de                                                 #
#                                                                                     #
#-------------------------------------------------------------------------------------#
#  Slicer 4.10.0                                                                      #
#  Updated: 16.9.2020                                                                 # 
#======================================================================================

import os, time, logging, unittest, shutil
import numpy as np, math
from __main__ import qt, ctk, slicer,vtk
from slicer.ScriptedLoadableModule import *
import SampleData

import VisSimCommon

# TODO:
# - Visualizing the interimediate steps.


# Terminology
#  img         : ITK image
#  imgNode     : Slicer Node
#  imgName     :  Filename without the path and without extension
#  imgPath     : wholePath + Filename and extension


#===================================================================
#                           Main Class
#===================================================================
class CochleaReg(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "Cochlea Registration"
        parent.categories = ["VisSimTools"]
        parent.dependencies = []
        parent.contributors = [
                               "Christopher Guy",
                               "Ibraheem Al-Dhamari",
                               "Michel Peltriauxe",
                               "Anna Gessler",
                               "Jasper Grimmig",
                               "Pepe Eulzer"
         ]
        parent.helpText            = " This module uses ACIR method to auatomatically register cochlea images"
        parent.acknowledgementText = " This work is sponsored by Cochlear as part of COMBS project "
        self.parent = parent
  #end def init
#end class CochleaReg

#===================================================================
#                           Main Widget
#===================================================================
class CochleaRegWidget(ScriptedLoadableModuleWidget):
  def setup(self):
    print(" ")
    print("=======================================================")
    print("   Automatic Cochlea Image Registration                ")
    print("=======================================================")

    ScriptedLoadableModuleWidget.setup(self)

    # to access logic class functions and setup global variables
    self.logic = CochleaRegLogic()

    # Set default VisSIm location in the user home
    #TODO: add option user-defined path when installed first time
    self.vsc   = VisSimCommon.VisSimCommonLogic()
    self.vsc.setGlobalVariables(0)

    self.fixedFiducialNode  = None 
    self.movingFiducialNode = None
    #-----------------------------------------------------------------
    #                     Create the GUI interface
    #-----------------------------------------------------------------
    # Create collapsible Button for registration, transformix and invert transform
    self.mainCollapsibleBtn = ctk.ctkCollapsibleButton()
    self.mainCollapsibleBtn.setStyleSheet("ctkCollapsibleButton { background-color: DarkSeaGreen  }")
    self.mainCollapsibleBtn.text = "ACIR: Automatic Cochlea Image Registration"
    self.layout.addWidget(self.mainCollapsibleBtn)
    self.mainFormLayout = qt.QFormLayout(self.mainCollapsibleBtn)

    # Create fixed Volume Selector
    self.fixedSelectorCoBx                        = slicer.qMRMLNodeComboBox()
    self.fixedSelectorCoBx.nodeTypes              = ["vtkMRMLScalarVolumeNode"]
    self.fixedSelectorCoBx.selectNodeUponCreation = True
    self.fixedSelectorCoBx.addEnabled             = False
    self.fixedSelectorCoBx.removeEnabled          = False
    self.fixedSelectorCoBx.noneEnabled            = False
    self.fixedSelectorCoBx.showHidden             = False
    self.fixedSelectorCoBx.showChildNodeTypes     = False
    self.fixedSelectorCoBx.setMRMLScene( slicer.mrmlScene )
    self.fixedSelectorCoBx.setToolTip("Pick the fixed volume")
    self.mainFormLayout.addRow("Fixed Volume: ", self.fixedSelectorCoBx)

    # Create moving Volume Selector
    self.movingSelectorCoBx                        = slicer.qMRMLNodeComboBox()
    self.movingSelectorCoBx.nodeTypes              = ["vtkMRMLScalarVolumeNode"]
    self.movingSelectorCoBx.selectNodeUponCreation = True
    self.movingSelectorCoBx.addEnabled             = False
    self.movingSelectorCoBx.removeEnabled          = False
    self.movingSelectorCoBx.noneEnabled            = False
    self.movingSelectorCoBx.showHidden             = False
    self.movingSelectorCoBx.showChildNodeTypes     = False
    self.movingSelectorCoBx.setMRMLScene( slicer.mrmlScene )
    self.movingSelectorCoBx.setToolTip("Pick the moving volume")
    self.mainFormLayout.addRow("Moving Volume: ", self.movingSelectorCoBx)

    # Create a time label
    self.timeLbl = qt.QLabel("                 Time: 00:00")
    self.timeLbl.setFixedWidth(500)
    self.tmLbl = self.timeLbl

    # Create a textbox for cochlea location
    # TODO activate input IJK values as well
    self.fixedPointEdt = qt.QLineEdit()
    self.fixedPointEdt.setFixedHeight(40)
    self.fixedPointEdt.setText("[0,0,0]")

    # Create a textbox for cochlea location
    # TODO activate input IJK values as well
    self.movingPointEdt = qt.QLineEdit()
    self.movingPointEdt.setFixedHeight(40)
    self.movingPointEdt.setText("[0,0,0]")

    # Create a cochlea locator button
    self.fixedFiducialBtn = qt.QPushButton("Pick cochlea location in fixed image    ")
    self.fixedFiducialBtn.setFixedHeight(40)
    self.fixedFiducialBtn.setToolTip("Pick the fixed fiducial point that will be the center of the cropped image")
    self.fixedFiducialBtn.connect('clicked(bool)', lambda: self.onInputFiducialBtnClick("F"))
    self.mainFormLayout.addRow( self.fixedFiducialBtn, self.fixedPointEdt)

    # Create a cochlea locator button
    self.movingFiducialBtn = qt.QPushButton("Pick cochlea location in moving image    ")
    self.movingFiducialBtn.setFixedHeight(40)
    self.movingFiducialBtn.setToolTip("Pick the moving fiducial point that will be the center of the cropped image")
    self.movingFiducialBtn.connect('clicked(bool)', lambda: self.onInputFiducialBtnClick("M"))
    self.mainFormLayout.addRow( self.movingFiducialBtn, self.movingPointEdt)

    # Add check box for disabling colors in the result of the registration
    self.colorsChkBox = qt.QCheckBox()
    self.colorsChkBox.text = "Disable colors"
    self.colorsChkBox.checked = False
    self.colorsChkBox.stateChanged.connect(self.OnColorsChkBoxChange)
    self.mainFormLayout.addRow(self.colorsChkBox)

    # Create a button to run registration
    self.applyBtn = qt.QPushButton("Run")
    self.applyBtn.setFixedHeight(50)
    self.applyBtn.setFixedWidth (250)
    self.applyBtn.setStyleSheet("QPushButton{ background-color: DarkSeaGreen  }")
    self.applyBtn.toolTip = ('How to use:' ' Load at least two images into Slicer. Pick cochlea locations using the buttons and the Slicer Fiducial tool ')
    self.applyBtn.connect('clicked(bool)', self.onApplyBtnClick)
    self.mainFormLayout.addRow(self.applyBtn, self.timeLbl)
    self.runBtn = self.applyBtn

    self.layout.addStretch(1) # Collapsible button is held in place when collapsing/expanding.

  #------------------------------------------------------------------------
  #                        Define GUI Elements Functions
  #------------------------------------------------------------------------
  def onInputFiducialBtnClick(self, volumeType):
      if not hasattr(self.vsc, 'vtVars'):
         self.vsc.setGlobalVariables(0)
       #end
      self.fixedVolumeNode=self.fixedSelectorCoBx.currentNode()
      self.movingVolumeNode=self.movingSelectorCoBx.currentNode()
      self.logic.fixedFiducialNode = None
      self.logic.movingFiducialNode = None
      #remove old nodes
      nodes = slicer.util.getNodesByClass('vtkMRMLMarkupsFiducialNode')
      for f in nodes:
          if (f.GetName() == "_CochleaLocation") :
               slicer.mrmlScene.RemoveNode(f)
          #endif
      #endfor
      # Create Fiducial Node for the cochlea location in both images
      if (volumeType=="F"):
         print(" ..... getting cochlea location in the fixed image")
         self.fixedFiducialBtn.setStyleSheet("QPushButton{ background-color: White  }")
         self.vsc.locateItem(self.fixedSelectorCoBx.currentNode(), self.fixedPointEdt,1, 0)
         self.fixedFiducialNode= self.vsc.inputFiducialNodes[1]
         self.fixedFiducialBtn.setStyleSheet("QPushButton{ background-color: DarkSeaGreen  }")
      elif (volumeType=="M"):
         print(" ..... getting cochlea location in the fixed image")
         self.vsc.locateItem(self.movingSelectorCoBx.currentNode(), self.movingPointEdt,2, 0)
         self.movingFiducialNode= self.vsc.inputFiducialNodes[2]
         self.movingFiducialBtn.setStyleSheet("QPushButton{ background-color: DarkSeaGreen  }")
    #endif
  #enddef


  # An option to control results displaying
  def OnColorsChkBoxChange(self):
        print("color is changed")
        self.vsc.fuseWithOutColor(self.colorsChkBox.checked)

  def onApplyBtnClick(self):
      self.runBtn.setText("...please wait")
      self.runBtn.setStyleSheet("QPushButton{ background-color: red  }")
      slicer.app.processEvents()
      self.stm=time.time()
      print("time:" + str(self.stm))
      self.timeLbl.setText("                 Time: 00:00")

      print(type(self.fixedFiducialNode))
      # create an option to use IJK point or fidicual node
      if (self.fixedFiducialNode is None) or (self.movingFiducialNode is None):
          registeredMovingVolumeNode =self.logic.run( self.fixedSelectorCoBx.currentNode(),self.movingSelectorCoBx.currentNode() )      
      else:
          registeredMovingVolumeNode =self.logic.runAcir( self.fixedSelectorCoBx.currentNode(),self.movingSelectorCoBx.currentNode(),self.fixedFiducialNode,self.movingFiducialNode )
      
      self.vsc.fuseTwoImages(self.fixedSelectorCoBx.currentNode(), registeredMovingVolumeNode, True)
      self.etm=time.time()
      tm=self.etm - self.stm
      self.timeLbl.setText("Time: "+str(tm)+"  seconds")
      self.runBtn.setText("Run")
      self.runBtn.setStyleSheet("QPushButton{ background-color: DarkSeaGreen  }")
      slicer.app.processEvents()
  #enddef

  def cleanup(self):
      pass
  #enddef

#===================================================================
#                           Logic
#===================================================================
class CochleaRegLogic(ScriptedLoadableModuleLogic):
  #--------------------------------------------------------------------------------------------
  #                       Registration Process
  #--------------------------------------------------------------------------------------------
  def initRun(self, fixedVolumeNode, movingVolumeNode,fixedFiducialNode=None, movingFiducialNode=None, customisedOutputPath=None, customisedParPath=None):  
      self.vsc   = VisSimCommon.VisSimCommonLogic()
      self.vsc.setGlobalVariables(0)
      self.vsc.removeOtputsFolderContents()

      if customisedOutputPath is not None: 
         self.vsc.vtVars['outputPath'] = customisedOutputPath
      if customisedParPath is not None: 
         self.vsc.vtVars['parsPath'] = customisedParPath

      print("fixedVolumeNode  = ", fixedVolumeNode.GetName())
      print("movingVolumeNode = ", movingVolumeNode.GetName())
      print("outputPath       = ", self.vsc.vtVars['outputPath'])
      print("parsPath         = ", self.vsc.vtVars['parsPath'])
      # results paths
      self.resTransPath  = os.path.join(self.vsc.vtVars['outputPath'] ,"TransformParameters.0.txt")
      self.resOldDefPath = os.path.join(self.vsc.vtVars['outputPath'] , "deformationField"+self.vsc.vtVars['imgType'])
      self.resDefPath    = os.path.join(self.vsc.vtVars['outputPath'] , movingVolumeNode.GetName()+"_dFld"+self.vsc.vtVars['imgType'])
      self.transNodeName = movingVolumeNode.GetName() + "_Transform"

      # Save original fixed and moving images
      if fixedVolumeNode.GetStorageNode() is None:
          self.fixedImgPath = os.path.join(self.vsc.vtVars['outputPath'], fixedVolumeNode.GetName()+".nrrd")
          slicer.util.saveNode(fixedVolumeNode, self.fixedImgPath)
      fixedPath = fixedVolumeNode.GetStorageNode().GetFileName()
      if movingVolumeNode.GetStorageNode() is None:
          self.movingImgPath = os.path.join(self.vsc.vtVars['outputPath'], movingVolumeNode.GetName()+".nrrd")
          slicer.util.saveNode(movingVolumeNode, self.movingImgPath)
      movingPath = movingVolumeNode.GetStorageNode().GetFileName()

      fixedRegTmpPath  = os.path.join(self.vsc.vtVars['outputPath'],fixedVolumeNode.GetName() +".nrrd")
      movingRegTmpPath = os.path.join(self.vsc.vtVars['outputPath'],movingVolumeNode.GetName()+".nrrd") 
      # copy images to VisSim folder
      shutil.copyfile(fixedPath , fixedRegTmpPath  )
      shutil.copyfile(movingPath, movingRegTmpPath)

      # create globale variables
      self.fixedRegTmpPath  = fixedRegTmpPath
      self.movingRegTmpPath =  movingRegTmpPath
      self.fixedPath        = fixedPath
      self.movingPath       = movingPath

  #TODO: use one simpler function to handle both cases 
  # This method perform the registration steps with cropped images 
  def runAcir(self, fixedVolumeNode, movingVolumeNode,fixedFiducialNode, movingFiducialNode, customisedOutputPath=None, customisedParPath=None):  
      logging.info('image registration started: with cropping')
      self.initRun(fixedVolumeNode, movingVolumeNode,fixedFiducialNode , movingFiducialNode, customisedOutputPath,customisedParPath) 

      # get globale variables
      fixedPath        =  self.fixedPath
      movingPath       =  self.movingPath
      fixedRegTmpPath  =  self.fixedRegTmpPath
      movingRegTmpPath =  self.movingRegTmpPath
      resTransPath     =  self.resTransPath
      resOldDefPath    =  self.resOldDefPath
      resDefPath       =  self.resDefPath
      transNodeName    =  self.transNodeName 

      # Get IJK point from the fiducial to use in cropping
      fixedPoint = self.vsc.ptRAS2IJK(fixedFiducialNode,fixedVolumeNode,0)
      print("run fixed point: ============================")
      print(fixedVolumeNode.GetName())
      print(fixedPoint)
      # TODO: add better condition
      if  np.sum(fixedPoint)== 0 :
            print("Error: select cochlea fixed point")
            return -1
      #endif
      fnm = os.path.join(self.vsc.vtVars['outputPath'] , fixedVolumeNode.GetName()+"_F_Cochlea_Pos.fcsv")
      sR = slicer.util.saveNode(fixedFiducialNode, fnm )
      movingPoint = self.vsc.ptRAS2IJK(movingFiducialNode,movingVolumeNode,0)
      print("run moving point: ============================")
      print(movingVolumeNode.GetName())
      print(movingPoint)
      # TODO: add better condition
      if  np.sum(fixedPoint)== 0 :
            print("Error: select cochlea moving point")
            return -1
      #endif
      fnm = os.path.join(self.vsc.vtVars['outputPath'] , movingVolumeNode.GetName()+"_M_Cochlea_Pos.fcsv")
      sR = slicer.util.saveNode(movingFiducialNode, fnm )
      #Remove old resulted nodes
      #for node in slicer.util.getNodes():
      #    if ( "result"   in [node].GetName() ): slicer.mrmlScene.RemoveNode(node) #endif
      #endfor
      # TODO: add better condition
      if  (np.sum(fixedPoint)== 0) and (np.sum(movingPoint)== 0) :
            #qt.QMessageBox.critical(slicer.util.mainWindow(),'SlicerCochleaRegistration', 'Cochlea locations are missing')
            print("Error: select cochlea points in fixed and moving images")
            return False
      #endif
      print((fixedPoint))   
      print(type(fixedPoint))
      fixedPointT = self.vsc.v2t(fixedPoint)
      movingPointT = self.vsc.v2t(movingPoint)
      print("=================== Cropping =====================")
      self.vsc.vtVars['fixedCropPath'] = self.vsc.runCropping(fixedVolumeNode, fixedPointT,self.vsc.vtVars['croppingLength'],  self.vsc.vtVars['RSxyz'],  self.vsc.vtVars['hrChk'],0)
      [success, croppedFixedNode] = slicer.util.loadVolume(self.vsc.vtVars['fixedCropPath'], returnNode=True)
      croppedFixedNode.SetName(fixedVolumeNode.GetName()+"_F_Crop")

      self.vsc.vtVars['movingCropPath'] = self.vsc.runCropping(movingVolumeNode, movingPointT,self.vsc.vtVars['croppingLength'],  self.vsc.vtVars['RSxyz'],  self.vsc.vtVars['hrChk'],0)
      [success, croppedMovingNode] = slicer.util.loadVolume(self.vsc.vtVars['movingCropPath'], returnNode=True)
      croppedMovingNode.SetName(movingVolumeNode.GetName()+"_M_Crop")
      print ("************  Register cropped moving image to cropped fixed image **********************")
      cTI = self.vsc.runElastix(self.vsc.vtVars['elastixBinPath'],self.vsc.vtVars['fixedCropPath'],  self.vsc.vtVars['movingCropPath'], self.vsc.vtVars['outputPath'], self.vsc.vtVars['parsPath'], self.vsc.vtVars['noOutput'], "336")
      resTransPathOld    = os.path.join(self.vsc.vtVars['outputPath'] , "TransformParameters.0.txt")
      resTransPathMod    = os.path.join(self.vsc.vtVars['outputPath'] , "TransformParametersMod.txt")
      resTransPathModInv = os.path.join(self.vsc.vtVars['outputPath'] , "TransformParametersModInv.txt")
      shutil.copyfile(resTransPathOld, resTransPathMod)
      shutil.copyfile(resTransPathOld, resTransPathModInv)
      #modify transform
      trfF= open(resTransPathMod,"rw") ;     parsLst = trfF.readlines() ;  trfF.close()
      #print(parsLst)
      fixedSize= fixedVolumeNode.GetImageData().GetDimensions() #[485, 485 , 121]
      fOrg = fixedVolumeNode.GetOrigin()   #[-30.3125 , -30.3125 , -30.0]      
      drs =  self.vsc.getDirs(fixedVolumeNode) 
      fixedOrg = [drs[0]*fOrg[0] , drs[4]*fOrg[1] , drs[8]*fOrg[2]]
      # apply the modified transform using transformix:
      #cTR = self.vsc.runTransformix(self.vsc.vtVars['transformixBinPath'],movingRegTmpPath, self.vsc.vtVars['outputPath'], resTransPathMod, self.vsc.vtVars['noOutput'], "339")
      #invert the transform then apply transfrmix
      cTR = self.vsc.runElxInvertTransform(resTransPathMod, resTransPathModInv, fixedRegTmpPath, self.vsc.vtVars['noOutput'], "339")
      trfF= open(resTransPathModInv,"w")
      for l in parsLst:   
          if ("(Size "   in l):        
             l = "(Size "   +str(fixedSize[0])+" "+str(fixedSize[1])+" "+str(fixedSize[2])+" )\n"
          #endif 
          if ("(Origin " in l):
             l = "(Origin " +str(fixedOrg[0]) +" "+str(fixedOrg[1]) +" "+str(fixedOrg[2]) +" )\n"
          #endif 
          trfF.write(l)
      trfF.close()
      fnm = os.path.join(self.vsc.vtVars['outputPath'],"result.nrrd")
      cTR = self.vsc.runTransformix(self.vsc.vtVars['transformixBinPath'],movingRegTmpPath, self.vsc.vtVars['outputPath'], resTransPathModInv, self.vsc.vtVars['noOutput'], "339")
      #[success, neweRegisteredMovingVolumeNode] = slicer.util.loadVolume(fnm, returnNode = True)
      #cTR = self.vsc.runTransformix(self.vsc.vtVars['transformixBinPath'],self.vsc.vtVars['movingCropPath'], self.vsc.vtVars['outputPath'], resTransPath, self.vsc.vtVars['noOutput'], "339")
      # rename fthe file:

      os.rename(resOldDefPath,resDefPath)
      resImagePath        = os.path.join(self.vsc.vtVars['outputPath'] , "result.nrrd")
      registeredImagePath = os.path.join(self.vsc.vtVars['outputPath'] , movingVolumeNode.GetName()+"_Registered.nrrd")
      os.rename(resImagePath,registeredImagePath)

      print ("************  Load deformation field Transform  **********************")
      [success, vtTransformNode] = slicer.util.loadTransform(resDefPath, returnNode = True)
      vtTransformNode.SetName(transNodeName)
      #print ("************  Transform The Original Moving image **********************")
      #movingVolumeNode.SetAndObserveTransformNodeID(vtTransformNode.GetID())
      #slicer.vtkSlicerTransformLogic().hardenTransform(movingVolumeNode)     # apply the transform
      #fnm = os.path.join(self.vsc.vtVars['outputPath'] , movingVolumeNode.GetName()+"_Registered.nrrd")
      #sR = slicer.util.saveNode(movingVolumeNode, fnm )
      [success, registeredMovingVolumeNode] = slicer.util.loadVolume(registeredImagePath, returnNode = True)
      print(registeredImagePath)
      print(success)
      registeredMovingVolumeNode.SetName(movingVolumeNode.GetName()+"_Registered")
      #remove the tempnode and load the original
      slicer.mrmlScene.RemoveNode(movingVolumeNode)
      [success, movingVolumeNode] = slicer.util.loadVolume(movingPath, returnNode = True)
      movingVolumeNode.SetName(os.path.splitext(os.path.basename(movingVolumeNode.GetStorageNode().GetFileName()))[0])
      if  (cTI==0) and (cTR==0):
          print("No error is reported during registeration ...")
      else:
           print("error happened during registration ")
      #endif

      #Remove temporary files and nodes:
      self.vsc.removeTmpsFiles()
      print("================= Cochlea registration is complete  =====================")
      logging.info('Processing completed')

      return registeredMovingVolumeNode
    #enddef

  def run(self, fixedVolumeNode, movingVolumeNode, customisedOutputPath=None, customisedParPath=None): 
      # This method perform the registration steps with no cropping
      logging.info('image registration started: no cropping')
      self.initRun(fixedVolumeNode, movingVolumeNode,None, None, customisedOutputPath, customisedParPath) 

      # get globale variables
      fixedPath        =  self.fixedPath
      movingPath       =  self.movingPath
      fixedRegTmpPath  =  self.fixedRegTmpPath
      movingRegTmpPath =  self.movingRegTmpPath
      resTransPath     =  self.resTransPath
      resOldDefPath    =  self.resOldDefPath
      resDefPath       =  self.resDefPath
      transNodeName    =  self.transNodeName 

      print ("************  Register  moving image to  fixed image **********************")
      cTI = self.vsc.runElastix(self.vsc.vtVars['elastixBinPath'],self.fixedRegTmpPath, self.movingRegTmpPath, self.vsc.vtVars['outputPath'], self.vsc.vtVars['parsPath'], self.vsc.vtVars['noOutput'], "336")
      resTransPathOld    = os.path.join(self.vsc.vtVars['outputPath'] , "TransformParameters.0.txt")

      fnm = os.path.join(self.vsc.vtVars['outputPath'],"result.nrrd")
      cTR = self.vsc.runTransformix(self.vsc.vtVars['transformixBinPath'],self.movingRegTmpPath, self.vsc.vtVars['outputPath'], self.resTransPath, self.vsc.vtVars['noOutput'], "339")

      os.rename(resOldDefPath,resDefPath)
      resImagePath        = os.path.join(self.vsc.vtVars['outputPath'] , "result.nrrd")
      registeredImagePath = os.path.join(self.vsc.vtVars['outputPath'] , movingVolumeNode.GetName()+"_Registered.nrrd")
      os.rename(resImagePath,registeredImagePath)

      print ("************  Load deformation field Transform  **********************")
      [success, vtTransformNode] = slicer.util.loadTransform(resDefPath, returnNode = True)
      vtTransformNode.SetName(transNodeName)
 
      [success, registeredMovingVolumeNode] = slicer.util.loadVolume(registeredImagePath, returnNode = True)
      print(registeredImagePath)
      print(success)
      registeredMovingVolumeNode.SetName(movingVolumeNode.GetName()+"_Registered")
      #remove the tempnode and load the original
      slicer.mrmlScene.RemoveNode(movingVolumeNode)
      [success, movingVolumeNode] = slicer.util.loadVolume(movingPath, returnNode = True)
      movingVolumeNode.SetName(os.path.splitext(os.path.basename(movingVolumeNode.GetStorageNode().GetFileName()))[0])
      if  (cTI==0) and (cTR==0):
          print("No error is reported during registeration ...")
      else:
           print("error happened during registration ")
      #endif

      #Remove temporary files and nodes:
      self.vsc.removeTmpsFiles()
      print("================= Cochlea registration is complete  =====================")
      logging.info('Processing completed')

      return registeredMovingVolumeNode
    #enddef

#===================================================================
#                           Test
#===================================================================
class CochleaRegTest(ScriptedLoadableModuleTest):
  def setUp(self):
      slicer.mrmlScene.Clear(0)
  #endef



  def runTest(self):
      self.setUp()
      fixedPoint  = [220,242,78]
      movingPoint = [196,217,93]
      #endif
      nodeNames='P100001_DV_L_a'
      fileNames='P100001_DV_L_a.nrrd'
      urisUniKo         = "https://cloud.uni-koblenz-landau.de/s/EwQiQidXqTcGySB/download"
      urisGitHub   = 'https://github.com/MedicalImageAnalysisTutorials/VisSimData/raw/master/P100001_DV_L_a.nrrd'
      uris = urisGitHub
      checksums='SHA256:d7cda4e106294a59591f03e74fbe9ecffa322dd1a9010b4d0590b377acc05eb5'

      tmpVolumeNode =  SampleData.downloadFromURL(uris, fileNames, nodeNames, checksums )[0]
      fixedImgPath  =  os.path.join(slicer.mrmlScene.GetCacheManager().GetRemoteCacheDirectory(),fileNames)
      slicer.mrmlScene.RemoveNode(tmpVolumeNode)
      nodeNames='P100001_DV_L_b'
      fileNames='P100001_DV_L_b.nrrd'
      urisUniKo    = "https://cloud.uni-koblenz-landau.de/s/qMG2WPjTXabzcbX/download"
      urisGitHub   = 'https://github.com/MedicalImageAnalysisTutorials/VisSimData/raw/master/P100001_DV_L_b.nrrd'
      uris = urisGitHub
      checksums='SHA256:9a5722679caa978b1a566f4a148c8759ce38158ca75813925a2d4f964fdeebf5'
      tmpVolumeNode =  SampleData.downloadFromURL(uris, fileNames, nodeNames, checksums )[0]
      movingImgPath  =  os.path.join(slicer.mrmlScene.GetCacheManager().GetRemoteCacheDirectory(),fileNames)
      slicer.mrmlScene.RemoveNode(tmpVolumeNode)

      fixedImgPath   = '/media/ibr/h25_2TB_C/ia_work/Cochlea2020/vsReg/srcImages/P100051_MR.nrrd'
      movingImgPath  = '/media/ibr/h25_2TB_C/ia_work/Cochlea2020/vsReg/srcImages/P100051_DV_R_a.nrrd'
      fixedPoint  = [165,240,34]
      movingPoint = [348,230,69]

      #self.testSlicerCochleaRegistration(fixedImgPath,movingImgPath)     
      self.testSlicerCochleaRegistration(fixedImgPath,movingImgPath, fixedPoint, movingPoint)
      
  #enddef
  def testSlicerCochleaDirectRegistration(self, fixedImgPath, movingImgPath, customisedOutputPath=None,customisedParPath=None):
      self.testSlicerCochleaRegistration(fixedImgPath,movingImgPath,None,None,customisedOutputPath,customisedParPath)  
   
  def testSlicerCochleaRegistration(self, fixedImgPath, movingImgPath, fixedPoint=None, movingPoint=None, customisedOutputPath=None,customisedParPath=None):

      self.delayDisplay("Starting testSlicerCochleaRegistration test")
      # record duration of the test
      self.stm=time.time()
      self.logic = CochleaRegLogic()
      self.vsc   = VisSimCommon.VisSimCommonLogic()
      #setGlobal variables.
      self.vsc.vtVars = self.vsc.setGlobalVariables(0)

      print("fixedImgPath         : ", fixedImgPath)
      print("movingImgPath        : ", movingImgPath)
      print("customisedOutputPath : ", customisedOutputPath)
      print("customisedParPath    : ", customisedParPath)
      fixedNodeName  = os.path.splitext(os.path.basename(fixedImgPath))[0]
      movingNodeName = os.path.splitext(os.path.basename(movingImgPath))[0]

      print("loading volumes ")  
      print(fixedImgPath)
      [success, fixedVolumeNode]  = slicer.util.loadVolume(fixedImgPath, returnNode=True)
      print(success)
      fixedVolumeNode.SetName(fixedNodeName)
      #endifelse
      [success, movingVolumeNode] = slicer.util.loadVolume(movingImgPath, returnNode=True)
      movingVolumeNode.SetName(movingNodeName)
      print(success)
      #endifelse
      # remove contents of output folder
      self.vsc.removeOtputsFolderContents()

      if  ( (not fixedPoint is None) and  (not movingPoint is None) ):
          print("creating points nodes")  
          # create a fiducial node for cochlea locations for cropping
          fixedPointRAS = self.vsc.ptIJK2RAS(fixedPoint , fixedVolumeNode)
          fixedFiducialNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
          fixedFiducialNode.CreateDefaultDisplayNodes()
          fixedFiducialNode.SetName("F_cochleaLocationPoint")
          fixedFiducialNode.AddFiducialFromArray(fixedPointRAS)
          fixedFiducialNode.SetNthFiducialLabel(0, "F_CochleaLocation")
    
          movingPointRAS = self.vsc.ptIJK2RAS(movingPoint , movingVolumeNode)
          movingFiducialNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
          movingFiducialNode.CreateDefaultDisplayNodes()
          movingFiducialNode.SetName("M_cochleaLocationPoint")
          movingFiducialNode.AddFiducialFromArray(movingPointRAS)
          movingFiducialNode.SetNthFiducialLabel(0, "M_CochleaLocation")

          # run the registration
          print("calling self.logic.runAcir")  
          registeredMovingVolumeNode = self.logic.runAcir(fixedVolumeNode, movingVolumeNode, fixedFiducialNode, movingFiducialNode, customisedOutputPath,customisedParPath)
      else:
          print("calling self.logic.run")  
          registeredMovingVolumeNode = self.logic.run(fixedVolumeNode,  movingVolumeNode, customisedOutputPath,customisedParPath)
              
      #endif

      #registeredMovingVolumeNode = self.logic.run(fixedVolumeNode,  movingVolumeNode)

      #display:
      try:
         self.vsc.fuseTwoImages(fixedVolumeNode, registeredMovingVolumeNode , True)
      except Exception as e:
             print("Can not display results! probably an external call ...")
             print(e)
      #endtry

      self.etm=time.time()
      tm=self.etm - self.stm
      print("Time: "+str(tm)+"  seconds")
      self.delayDisplay('Test testSlicerCochleaRegistration passed!')
  #enddef



#endclass
