Installation Instructions:
write the insturctions.


Execute the program:

1.- Open command prompt and go to Desktop/kelvinprobegui/
2.- Activate python environmnet: 
	conda activate guidev
3.- Run 
	python main.py

Making a Measurment:
# WF of Au mesh is calculated at 4.51 +/- 0.04 eV
# I think Au mesh at aroud 4.51-4.3 for gradient of 3.5 +/- 0.2
# Fresh HOPG work function is 4.55 (im using a mean of different reported values)) 
# We measured -0.05 eV . WF_sample = WF_mesh + V_Bias
# We measure 0.151 @ -3.376 Gradient HOPG 4.55 eV so WfAu = 4.40
# We measure 0.163 @ -3.784 Gra  dient                 WfAu = 4.39
# We measured 0.025 @ -4.55 Gradient WfAu = 4.525 eV.


1.- Lower mesh to desired height.
2.- Check that the oscillator frequency has not moved to much.