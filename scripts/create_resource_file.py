#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py

import os
print("Creating resources.qrc file")
res_file = '../resources.qrc'
if os.path.exists(res_file):
    os.remove(res_file)
os.system('touch {}'.format(res_file))
files = os.listdir('../resources')
with open(res_file, 'w') as f:
    f.write('<!DOCTYPE RCC>\n<RCC version="1.0">\n')
    f.write('\t<qresource>\n')
    for file in files:
        f.write('\t\t<file alias="{0}">resources/{0}</file>\n'.format(file))
    f.write('\t</qresource>\n')
    f.write('</RCC>\n')
print("resources.qrc is created.")
