# Mirror Weights for Maya
This is a Maya tool that can be used to copy/mirror weights from one attribute to another one. It works for any float/double array attributes.

<img width="1623" alt="image" src="https://github.com/azagoruyko/mirrorWeights/assets/9614751/9207aa2f-42fe-447e-9912-ea35714160cb">


## How to run
```python
import sys
path = "YOUR_PATH/mirrorWeights"
if path not in sys.path:
  sys.path.append(path)  # mirrorWeights folder should be added to sys.path to load it as a module

import mirrorWeights
mirrorWeights.show()
```
Or add mirrorWeights folder to your scripts path and run as
```python
import mirrorWeights
mirrorWeights.show()
```
