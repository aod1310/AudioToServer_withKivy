# kivy install
conda install kivy -c conda-forge

# buildozer install
pip install buildozer

# auduiostream install
git clone https://github.com/kivy/audiostream.git\\
cd ./audiostream\\
python setup.py install\\
- pre-requires -
apt-get install gcc, g++, libsdl1.2-dev libsdl-image1.2-dev libsdl-mixer1.2-dev libsdl-net1.2-dev libsdl-ttf2.0-dev <-- SDL library

# pyjnius install
pip install pyjnius



# AudioToServer_withKivy

OS : LINUX(Ubuntu 18.04LTS)
Language : Python 3.6.9
Package : Kivy, audiostream


Using Android Microphone, Send recording audio stream to Server.


-- Issues!
: cannot dlopen locate symbol : SDL_Android_GetJniEnv

this error is from unmatch version between SDL2.0 and audiostream(kivy)

so, First, your/buildozer/directory/other_builds/audiostream/platform/android_ext.h

extern JNIEnv *SDL_ANDROID_GetJNIEnv() <--- remove
and, method 'create_jni_env()' in JNIEnv *env = SDL_ANDROID_GetJNIEnv() --> revise --> JNIEnv *env = SDL_AndroidGetJNIEnv();

SDL_AndroidGetJNIEnv(); this is in SDL.h, returns JNIEnv type.


second, same directory(audiostream/platform), you can find "java" dir, and inside that, there is 'org'.
copy that, and paste to dist/src/main/java

and, audiostream/build, your/buildozer/directory/python-installs <- remove them.
and rebuild.

if you see the logcat with usb debugging, enter below on shell
'buildozer android debug deploy run logcat | grep python.



To Use BlueTooth Headset.
Revise 'MainActivity.java' file.

inside of the file, 'onCreate()' method is existed.

declare 'AudioManager' and call startBluetoothSco()




