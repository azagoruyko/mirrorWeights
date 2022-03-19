# Mirror Weights for Maya
This is a Maya tool that can be used to copy/mirror weights from one attribute to another one. It works for any float/double array attributes.

![mirrorWeights](https://user-images.githubusercontent.com/9614751/159112043-65674254-fd29-406e-81b0-d6716b82a38f.PNG)

## UI description

**Mirror?** Whether to mirror from left to right or just *copy* weights.<br>
**Clamp** Clamp weights from 0 to 1.<br>
**Edit sets** Update destination deformer's set, i.e. add or remove vertices.<br>
**Fast** Experimental feature. It can be used for very large arrays.<br>
**Src deformer** A deformer to copy/mirror weights from.<br>
**Dest deformer** The destination deformer.<br>
**Src shape index** For multishape deformers (i.e. a single deformer that deforms multiple geometries).<br>
**Dest shape index** Destination shape index.<br>
**Attr template** Predefined attribute selector.<br>
**Src attr** Actual attribute to copy weights from.<br>
**Dest attr** Actual destination attribute the weights to be copied to.<br>
