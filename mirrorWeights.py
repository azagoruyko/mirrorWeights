import pymel.core as pm
import pymel.api as api
import maya.cmds as cmds

import time
import re

mirrorWeights_attrTemplates = {"deformer": "weightList[0].weights",
                               "blendShape": "inputTarget[0].baseWeights",
                               "blendShape targets": "inputTarget[0].inputTargetGroup[5].targetWeights"}

def clamp(val, mn, mx):
    if val < mn:
        return mn
    elif val > mx:
        return mx
    else:
        return val
        
def mirrorWeights(srcDeformer,
                  destDeformer,
                  mirror,
                  srcAttr="weightList[0].weights",
                  destAttr="weightList[0].weights",
                  doClamp=False,
                  editSets=False,
                  srcShapeIndex=0,
                  destShapeIndex=0,
                  fast=False):
    
    if srcDeformer == destDeformer and srcAttr == destAttr and not mirror:  # do nothing when copy to itself
        return
    
    srcMesh = pm.PyNode(srcDeformer).inputShapeAtIndex(srcShapeIndex)
    destMesh = pm.PyNode(destDeformer).inputShapeAtIndex(destShapeIndex)
    
    # do not mirror if both attributes are empty (default)
    if not pm.PyNode("%s.%s" % (srcDeformer, srcAttr)).get() and not pm.PyNode("%s.%s" % (destDeformer, destAttr)).get():
        pm.warning("mirrorWeights: both attributes are empty ('%s' and '%s'). Ignored" % (srcAttr, destAttr))
        return

    print "%s from '%s.%s' to '%s.%s' using srcMesh=%s, destMesh=%s" % ("Mirror" if mirror else "Copy",
                                                                        srcDeformer,
                                                                        srcAttr,
                                                                        destDeformer,
                                                                        destAttr,
                                                                        srcMesh,
                                                                        destMesh)        
    destPoints = api.MPointArray()
    destMeshFn = api.MFnMesh(destMesh.__apimdagpath__())
    destMeshFn.getPoints(destPoints, api.MSpace.kWorld)
    
    srcMeshFn = api.MFnMesh(srcMesh.__apimdagpath__())
    meshIntersector = api.MMeshIntersector()

    srcMeshPath = srcMesh.__apimdagpath__()
    srcMeshPath.extendToShape()

    meshIntersector.create(srcMeshPath.node(), srcMeshPath.inclusiveMatrix())

    srcSet = pm.PyNode(srcDeformer).deformerSet()
    destSet = pm.PyNode(destDeformer).deformerSet()

    srcDeformerGeo = pm.PyNode(srcDeformer).getOutputGeometry()[srcShapeIndex]
    destDeformerGeo = pm.PyNode(destDeformer).getOutputGeometry()[destShapeIndex]

    srcAttrValues = [0] * srcMeshFn.numVertices()

    isSetEmpty = cmds.sets(srcSet.name(), q=True) == None

    for i in range(srcMeshFn.numVertices()):
        if isSetEmpty or cmds.sets("%s.vtx[%s]" % (srcDeformerGeo, i), im=srcSet.name()):
            w = cmds.getAttr("%s.%s[%s]" % (srcDeformer, srcAttr, i))
            srcAttrValues[i] = w

    scriptUtil = api.MScriptUtil()

    destSet2add = []
    destSet2remove = []

    components = pm.ls(sl=True, fl=True, type="float3")  # get vertices
    indices = set([v.indices()[0] for v in components])

    weights = [0] * destPoints.length()

    gMainProgressBar = pm.mel.eval('$tmpVar=$gMainProgressBar')
    pm.progressBar(gMainProgressBar, e=True, beginProgress=True, isInterruptable=False,
                     status="%s weights %s.%s >> %s.%s" % ("Mirror" if mirror else "Copy", srcDeformer, srcAttr, destDeformer, destAttr),
                     maxValue=destPoints.length())
    
    ProgressBarUpdatePercent = int(destPoints.length() * 0.15)  # 15%

    startTime = time.time()
    for i in range(destPoints.length()):
        if i % ProgressBarUpdatePercent == 0:
            pm.progressBar(gMainProgressBar, e=True, progress=i)

        if indices and i not in indices:
            continue

        mirrorPoint = api.MPoint(destPoints[i])

        if mirror:
            if srcDeformer == destDeformer and destPoints[i].x > 0:
                continue

            mirrorPoint.x *= -1

        poim = api.MPointOnMesh()
        meshIntersector.getClosestPoint(mirrorPoint, poim)

        scriptUtil.createFromInt(0, 0, 0, 0)
        vertices3 = scriptUtil.asIntPtr()

        srcMeshFn.getPolygonTriangleVertices(poim.faceIndex(), poim.triangleIndex(), vertices3)

        u = api.floatPtr()
        v = api.floatPtr()
        poim.getBarycentricCoords(u, v)
        u = u.value()
        v = v.value()

        w = 1 - u - v
        # -----------
        v1 = scriptUtil.getIntArrayItem(vertices3, 0)
        v2 = scriptUtil.getIntArrayItem(vertices3, 1)
        v3 = scriptUtil.getIntArrayItem(vertices3, 2)

        weights[i] = srcAttrValues[v1] * u + srcAttrValues[v2] * v + srcAttrValues[v3] * w

        if doClamp:
            weights[i] = clamp(weights[i], 0.0, 1.0)

        if editSets:
            if weights[i] > 0.001:
                if not cmds.sets("%s.vtx[%s]" % (destDeformerGeo, i), im=destSet.name()):
                    destSet2add.append("%s.vtx[%s]" % (destDeformerGeo, i))
            else:
                destSet2remove.append("%s.vtx[%s]" % (destDeformerGeo, i))

    pm.progressBar(gMainProgressBar, e=True, endProgress=True)

    if editSets:
        if destSet2add:
            cmds.sets(destSet2add, add=destSet.name())

        if destSet2remove:
            cmds.sets(destSet2remove, remove=destSet.name())

    if fast:
        plug = pm.PyNode("%s.%s"%(destDeformer, destAttr)).__apimplug__()
        plugHandle = plug.asMDataHandle()
        handle = api.MDataHandle(plugHandle) # copy
        arrayHandle = api.MArrayDataHandle(handle)
        builder = arrayHandle.builder()
            
    for i in range(destPoints.length()):
        if indices and i not in indices:
            continue

        if mirror and srcDeformer == destDeformer and srcAttr == destAttr and destPoints[i].x > 0:
            continue

        if fast:
            builder.addElement(i).setFloat(weights[i])
        else:
            cmds.setAttr("%s.%s[%s]" % (destDeformer, destAttr, i), weights[i])

    if fast:
        arrayHandle.set(builder)
        plug.setMDataHandle(handle)

        plug.destructHandle(plugHandle)
            
    print "MirrorWeights time: %s" % (time.time() - startTime)

def doItClicked():
    mirror = cmds.checkBox("mirrorWeights_mirror", q=True, v=True)
    doClamp = cmds.checkBox("mirrorWeights_doClamp", q=True, v=True)
    editSets = cmds.checkBox("mirrorWeights_editSets", q=True, v=True)
    fast = cmds.checkBox("mirrorWeights_fast", q=True, v=True)

    srcAttr = cmds.textFieldGrp("mirrorWeights_srcAttr", q=True, text=True)
    destAttr = cmds.textFieldGrp("mirrorWeights_destAttr", q=True, text=True)

    srcDeformer = cmds.textFieldButtonGrp("mirrorWeights_srcDeformer", q=True, text=True)
    destDeformer = cmds.textFieldButtonGrp("mirrorWeights_destDeformer", q=True, text=True)

    srcShapeIndex = pm.intFieldGrp("mirrorWeights_srcShapeIndex", q=True, v1=True)
    destShapeIndex = pm.intFieldGrp("mirrorWeights_destShapeIndex", q=True, v1=True)
    
    if not srcDeformer or not destDeformer or not srcAttr or not destAttr:
        api.MGlobal.displayError("Please fill all the fields")
        return

    if not cmds.objExists(srcDeformer) or not cmds.objExists(destDeformer):
        api.MGlobal.displayError("Source or destination deformer doesn't exist")
        return

    srcAttrsList = srcAttr.split()
    destAttrsList = destAttr.split()

    if len(srcAttrsList) != len(destAttrsList):
        api.MGlobal.displayError("Source and destination attributes are not equal")
        return

    for i, (sa, da) in enumerate(zip(srcAttrsList, destAttrsList)):
        if not cmds.objExists("%s.%s[0]" % (srcDeformer, sa)):
            api.MGlobal.displayWarning("Source attribute '%s.%s' doesn't exist. Ignored" % (srcDeformer, sa))
            continue

        elif not cmds.objExists("%s.%s[0]" % (destDeformer, da)):
            api.MGlobal.displayWarning("Destination attribute '%s.%s' doesn't exist. Ignored" % (destDeformer, da))
            return

        mirrorWeights(srcDeformer, destDeformer, mirror, sa, da, doClamp, editSets if i == 0 else False, srcShapeIndex, destShapeIndex, fast)

def getSelected(field):
    ls = cmds.ls(sl=True)

    if ls:
        cmds.textFieldGrp(field, e=True, text=ls[0])

def setToField(field, symField, val):
    if field:
        cmds.textFieldGrp(field, e=True, text=val)

    isMirror = cmds.checkBox("mirrorWeights_mirror", q=True, v=True)
    src = cmds.textFieldButtonGrp("mirrorWeights_srcDeformer", q=True, text=True)
    dest = cmds.textFieldButtonGrp("mirrorWeights_destDeformer", q=True, text=True)

    if symField and isMirror:
        cmds.textFieldGrp(symField, e=True, text=val.replace("L_", "R_"))

def mirrorWeights_changeTemplate():
    t = cmds.optionMenu("mirrorWeights_template", q=True, v=True)
    attr = mirrorWeights_attrTemplates[t]
    cmds.textFieldGrp("mirrorWeights_srcAttr", e=True, text=attr)
    cmds.textFieldGrp("mirrorWeights_destAttr", e=True, text=attr)

def deleteWindow(wnd):
    if pm.windowPref(wnd, exists=True):
        pm.windowPref(wnd, remove=True)

    if pm.window(wnd, exists=True):
        pm.deleteUI(wnd, wnd=True)    

def updatePopupMenu(textField):
    popup = cmds.textFieldButtonGrp(textField, q=True, pma=True)
    if popup:
        for mi in cmds.popupMenu(popup, q=True, ia=True):
            if cmds.menuItem(mi, q=True, label=True) != "Update":
                cmds.deleteUI(mi, mi=True)

        popup = popup[0]
    else:
        popup = cmds.popupMenu(parent=textField)
        cmds.menuItem(l="Update", p=popup, c=pm.Callback(updatePopupMenu, textField))

    ls = cmds.ls(sl=True)
    if not ls:
        return

    sel = ls[0]

    cmds.menuItem(d=True, p=popup)

    for d in pm.listHistory(sel, pruneDagObjects=True, interestLevel=1):
        if "deformerSet" not in dir(d) or re.search("tweak", d.name()):
            continue

        if textField == "mirrorWeights_srcDeformer":
            cmds.menuItem(l=d.name(), p=popup, c=pm.Callback(setToField, "mirrorWeights_srcDeformer", 'mirrorWeights_destDeformer', d.name()))
        else:
            cmds.menuItem(l=d.name(), p=popup, c=pm.Callback(setToField, textField, '', d.name()))

def show():
    if pm.window("mirrorWeights_window", exists=True):
        updatePopupMenu("mirrorWeights_srcDeformer")
        updatePopupMenu("mirrorWeights_destDeformer")        
        pm.showWindow("mirrorWeights_window")
        return
        
    pm.window("mirrorWeights_window", title="Mirror weights", width=100, height=100, sizeable=False, ret=True)
    pm.columnLayout(adj=True)
    pm.rowLayout(nc=4)
    pm.checkBox("mirrorWeights_mirror", l="Mirror? (from X to -X)", v=1)
    pm.checkBox("mirrorWeights_doClamp", l="Clamp? (0..1)", v=1)
    pm.checkBox("mirrorWeights_editSets", l="Edit sets", v=0)
    pm.checkBox("mirrorWeights_fast", l="Fast", v=0)
    pm.setParent("..")

    pm.textFieldButtonGrp("mirrorWeights_srcDeformer",
                            cw3=[140, 300, 40],
                            label="Src deformer",
                            text="",
                            buttonLabel="<<",
                            bc=pm.Callback(getSelected, 'mirrorWeights_srcDeformer'))

    updatePopupMenu("mirrorWeights_srcDeformer")

    pm.textFieldButtonGrp("mirrorWeights_destDeformer",
                            cw3=[140, 300, 40],
                            label="Dest deformer",
                            text="",
                            buttonLabel="<<",
                            bc=pm.Callback(getSelected, 'mirrorWeights_destDeformer'))

    updatePopupMenu("mirrorWeights_destDeformer")
    
    pm.rowLayout(nc=2)
    pm.intFieldGrp("mirrorWeights_srcShapeIndex", label="Src shape index", v1=0)
    pm.intFieldGrp("mirrorWeights_destShapeIndex",  label="Dest shape index", v1=0)
    pm.setParent("..")

    pm.optionMenu("mirrorWeights_template", label="Attr template", cc=pm.Callback(mirrorWeights_changeTemplate))

    for k in sorted(mirrorWeights_attrTemplates):
        pm.menuItem(label=k)

    pm.optionMenu("mirrorWeights_template", e=True, sl=3)

    pm.textFieldGrp("mirrorWeights_srcAttr", cw2=[120, 330], label="Src attr", text="weightList[0].weights")
    pm.textFieldGrp("mirrorWeights_destAttr", cw2=[120, 330], label="Dest attr", text="weightList[0].weights")

    pm.button("mirrorWeights_doItButton", l="Do it", c=pm.Callback(doItClicked))
    pm.showWindow("mirrorWeights_window")
