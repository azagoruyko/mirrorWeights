import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om

mirrorWeights_attrTemplates = {"deformer": "weightList[0].weights",
                               "blendShape": "inputTarget[0].baseWeights",
                               "blendShape targets": "inputTarget[0].inputTargetGroup[5].targetWeights"}

def Callback(f, *args, **kwargs):
    return lambda *_,**__: f(*args, **kwargs)

def getMDagPath(node):
    sel = om.MSelectionList()
    sel.add(node)
    return sel.getDagPath(0)

def clamp(val, mn, mx):
    if val < mn:
        return mn
    elif val > mx:
        return mx
    else:
        return val

def mirrorWeights(srcMesh, srcDeformer, destMesh, destDeformer, srcAttr="weightList[0].weights", destAttr="weightList[0].weights", mirror=True, doClamp=False):
    srcMesh = cmds.deformableShape(srcMesh, og=True)[0].split(".")[0]
    destMesh = cmds.deformableShape(destMesh, og=True)[0].split(".")[0]

    destPoints = om.MPointArray()
    destMeshFn = om.MFnMesh(getMDagPath(destMesh))
    destPoints = destMeshFn.getPoints(om.MSpace.kWorld)

    srcMeshPath = getMDagPath(srcMesh)
    srcMeshPath.extendToShape()
    srcMeshFn = om.MFnMesh(srcMeshPath)

    meshIntersector = om.MMeshIntersector()
    meshIntersector.create(srcMeshPath.node(), srcMeshPath.inclusiveMatrix())

    srcAttrValues = [0] * srcMeshFn.numVertices
    for i in range(srcMeshFn.numVertices):
        srcAttrValues[i] = cmds.getAttr("{}.{}[{}]".format(srcDeformer, srcAttr, i))

    components = cmds.ls(sl=True, fl=True, type="float3")  # get vertices
    indices = set([v.indices()[0] for v in components])

    gMainProgressBar = mel.eval("$tmpVar=$gMainProgressBar")
    cmds.progressBar(gMainProgressBar, e=True, beginProgress=True, isInterruptable=False,
                     status="{} weights {}.{} >> {}.{}".format("Mirror" if mirror else "Copy", srcDeformer, srcAttr, destDeformer, destAttr),
                     maxValue=len(destPoints))

    progressBarUpdatePercent = int(len(destPoints) * 0.15)

    for i in range(len(destPoints)):
        if i%progressBarUpdatePercent == 0:
            cmds.progressBar(gMainProgressBar, e=True, progress=i)

        if indices and i not in indices:
            continue

        mirrorPoint = om.MPoint(destPoints[i])
        if mirror:
            if srcDeformer == destDeformer and srcMesh == destMesh and destPoints[i].x > 0:
                continue
            mirrorPoint.x *= -1

        poim = meshIntersector.getClosestPoint(mirrorPoint, om.MSpace.kWorld)

        v1, v2, v3 = srcMeshFn.getPolygonTriangleVertices(poim.face, poim.triangle)
        u, v = poim.barycentricCoords
        w = 1 - u - v
        weight = srcAttrValues[v1] * u + srcAttrValues[v2] * v + srcAttrValues[v3] * w

        if doClamp:
            weight = clamp(weight, 0.0, 1.0)

        cmds.setAttr("{}.{}[{}]".format(destDeformer, destAttr, i), weight)

    cmds.progressBar(gMainProgressBar, e=True, endProgress=True)

def doIt():
    srcMesh = cmds.textFieldButtonGrp("mirrorWeights_srcMesh", q=True, text=True)
    srcDeformer = cmds.textFieldButtonGrp("mirrorWeights_srcDeformer", q=True, text=True)
    destMesh = cmds.textFieldButtonGrp("mirrorWeights_destMesh", q=True, text=True)
    destDeformer = cmds.textFieldButtonGrp("mirrorWeights_destDeformer", q=True, text=True)

    mirror, doClamp = cmds.checkBoxGrp("mirrorWeights_options", q=True, va2=True)

    srcAttr = cmds.textFieldGrp("mirrorWeights_srcAttr", q=True, text=True)
    destAttr = cmds.textFieldGrp("mirrorWeights_destAttr", q=True, text=True)

    if not srcDeformer or not destDeformer or not srcAttr or not destAttr:
        om.MGlobal.displayError("Please fill all the fields")
        return

    if not cmds.objExists(srcDeformer) or not cmds.objExists(destDeformer):
        om.MGlobal.displayError("Source or destination deformer doesn't exist")
        return

    if not cmds.objExists("{}.{}".format(srcDeformer, srcAttr)):
        om.MGlobal.displayError("Source attribute '{}.{}' doesn't exist".format(srcDeformer, srcAttr))
        return
    
    if not cmds.objExists("{}.{}".format(destDeformer, destAttr)):
        om.MGlobal.displayError("Destination attribute '{}.{}' doesn't exist".format(destDeformer, destAttr))
        return    

    mirrorWeights(srcMesh, srcDeformer, destMesh, destDeformer, srcAttr, destAttr, mirror, doClamp)

def updatePopupMenu(textField):
    def setField(field, value):
        cmds.textFieldGrp(field, e=True, text=value)

    popup = cmds.textFieldButtonGrp(textField, q=True, pma=True)
    if popup:
        for mi in cmds.popupMenu(popup, q=True, ia=True):
            cmds.deleteUI(mi, mi=True)
        popup = popup[0]
    else:
        popup = cmds.popupMenu(parent=textField)

    ls = cmds.ls(sl=True)
    if ls:
        for d in cmds.listHistory(ls[0], pruneDagObjects=True, interestLevel=1):        
            cmds.menuItem(l=d, p=popup, c=Callback(setField, textField, d))

def show():
    def deleteWindow(wnd):
        if cmds.windowPref(wnd, exists=True):
            cmds.windowPref(wnd, remove=True)

        if cmds.window(wnd, exists=True):
            cmds.deleteUI(wnd, wnd=True)

    def getSelected(field):
        ls = cmds.ls(sl=True)
        if ls:
            cmds.textFieldGrp(field, e=True, text=ls[0])

    def getDeformer(field, deformerField):
        getSelected(field)
        updatePopupMenu(deformerField)

    def changeTemplate(t):
        attr = mirrorWeights_attrTemplates[t]
        cmds.textFieldGrp("mirrorWeights_srcAttr", e=True, text=attr)
        cmds.textFieldGrp("mirrorWeights_destAttr", e=True, text=attr)

    if cmds.window("mirrorWeights_window", exists=True):
        cmds.showWindow("mirrorWeights_window")
        return

    cmds.window("mirrorWeights_window", title="Mirror weights", width=100, height=100, sizeable=False, ret=True)
    cmds.columnLayout(adj=True)

    cmds.textFieldButtonGrp("mirrorWeights_srcMesh", cw3=[100, 150, 40], label="Src mesh", text="", buttonLabel="<<", bc=Callback(getDeformer, "mirrorWeights_srcMesh", "mirrorWeights_srcDeformer"))
    cmds.textFieldButtonGrp("mirrorWeights_srcDeformer", cw3=[100, 150, 40], label="Src deformer", text="", buttonLabel="<<", bc=Callback(getSelected, "mirrorWeights_srcDeformer"))

    cmds.textFieldButtonGrp("mirrorWeights_destMesh", cw3=[100, 150, 40], label="Dest mesh", text="", buttonLabel="<<", bc=Callback(getDeformer, "mirrorWeights_destMesh", "mirrorWeights_destDeformer"))
    cmds.textFieldButtonGrp("mirrorWeights_destDeformer",cw3=[100, 150, 40], label="Dest deformer", text="",buttonLabel="<<", bc=Callback(getSelected, "mirrorWeights_destDeformer"))
    
    cmds.checkBoxGrp("mirrorWeights_options", numberOfCheckBoxes=2, label="Options", labelArray2=["Mirror", "Clamp"], cw3=[100, 70, 70], v1=True, v2=False)

    cmds.optionMenu("mirrorWeights_template", label="Attr template", cc=changeTemplate)
    for k in mirrorWeights_attrTemplates:
        cmds.menuItem(label=k)
    cmds.optionMenu("mirrorWeights_template", e=True, sl=list(mirrorWeights_attrTemplates.keys()).index("deformer")+1)

    cmds.textFieldGrp("mirrorWeights_srcAttr", cw2=[70, 200], label="Src attr", text="weightList[0].weights")
    cmds.textFieldGrp("mirrorWeights_destAttr", cw2=[70, 200], label="Dest attr", text="weightList[0].weights")

    cmds.button(l="Do it", c=Callback(doIt))
    cmds.showWindow("mirrorWeights_window")

show()