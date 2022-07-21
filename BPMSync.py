import obspython as obs
import aubio
import numpy as np
import pyaudio

media_source = ""
interval = 1
original_speed = 0
buff_size = 256

class BPMTracker:

    def __init__(self):
        self.p = pyaudio.PyAudio()
        
        default_device_index = -1

        for i in range(0, self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            print(str(info["index"]) + ": \t %s \n \t %s \n" % (info["name"], self.p.get_host_api_info_by_index(info["hostApi"])["name"]))

            if default_device_index == -1 and (self.p.get_host_api_info_by_index(info["hostApi"])["name"]).find("WASAPI") != -1:
                default_device_index = info["index"]

        if(default_device_index == -1):
            print("Located no devices, quitting.")
            exit()

        device_id = int(default_device_index)

        device_info = self.p.get_device_info_by_index(default_device_index)

        is_wasapi = (self.p.get_host_api_info_by_index(device_info["hostApi"])["name"]).find("WASAPI") != -1

        if is_wasapi:
            useloopback = True;
        else:
            print("failed to find output, exiting.")
            exit()

        channel_count = device_info["maxInputChannels"] if (device_info["maxOutputChannels"] < device_info["maxInputChannels"]) else device_info["maxOutputChannels"]
        samplerate = device_info["defaultSampleRate"]
        self.stream = self.p.open(format = pyaudio.paFloat32,
                             channels = channel_count,
                             rate = int(samplerate),
                             input = True,
                             frames_per_buffer = buff_size,
                             input_device_index = device_info["index"],
                             stream_callback = self._pyaudio_callback,
                             as_loopback = True)
        self.tempo = aubio.tempo("default",buff_size,buff_size,44100)
        self.bpm = 1

    def _pyaudio_callback(self,
                          in_data,
                          frame_count,
                          time_info,status):
        signal = np.frombuffer(in_data,dtype=np.float32,count=buff_size)
        beat = self.tempo(signal)
        if beat[0]:
            self.bpm = self.tempo.get_bpm()
        return None, pyaudio.paContinue

    def get_curr_bpm(self):
        return self.bpm

    def __del__(self):
        self.stream.close()
        self.p.terminate()

bpm_tracker = BPMTracker()

def update_bpm(): 
    global media_source
    global original_speed
    source = obs.obs_get_source_by_name(media_source)
    curr_bpm = bpm_tracker.get_curr_bpm()
    if source is not None:
        data_container = obs.obs_data_create()
        print("Current BPM is: {}".format(curr_bpm))
        if curr_bpm is not 0:
            target_speed = int(curr_bpm/100 * original_speed)
            obs.obs_data_set_int(data_container, 
                                 "speed_percent", 
                                 target_speed)
        else:
            #fallback for if everything breaks
            obs.obs_data_set_int(data_container, "speed_percent", 5)
        obs.obs_source_update(source, data_container)
    obs.obs_source_release(source)

def refresh_pressed(props, prop):
	update_bpm()

def script_descritption():
        return "Media Speed\nThis script attepmts to synchronise the playback of a media file to the beat of your desktop audio stream.\nDO NOT USE THIS WITH MEDIA THAT HAS AUDIO, I HAVE NO IDEA WHAT WILL HAPPEN.\nSome tweaking of playback speeds on your part to synchronise it may be necessary."

def script_update(settings):
    global media_source
    global original_speed
    global interval

    media_source = obs.obs_data_get_string(settings, "source_image")
    interval = obs.obs_data_get_int(settings, "interval")
    original_speed = obs.obs_data_get_int(settings, "speed_percent")
    obs.timer_remove(update_bpm)
    source = obs.obs_get_source_by_name(media_source)
   
    if source is not None:
       source_id = obs.obs_source_get_unversioned_id(source)
       if source_id == "ffmpeg_source":
            obs.timer_add(update_bpm, interval * 1000)

def script_defaults(settings):
    obs.obs_data_set_default_int(settings, "interval", 3)
    obs.obs_data_set_default_int(settings, "speed_percent", 100)

def script_properties():
    properties = obs.obs_properties_create()
    obs.obs_properties_add_int(properties,
                               "interval", 
                               "Update Interval (Seconds)", 
                               1, 10, 1)
    # going to create a list of media sources and speed properties once the beat detection is working, then i can actually whip this up
    p = obs.obs_properties_add_list(properties, 
                                    "source_image", 
                                    "Media Source", 
                                    obs.OBS_COMBO_TYPE_EDITABLE, 
                                    obs.OBS_COMBO_FORMAT_STRING)
    obs.obs_properties_add_int_slider(properties, 
                                      "speed_percent", 
                                      "Base Speed", 
                                      1, 200, 1)
    sources = obs.obs_enum_sources()
    if sources is not None:
        for source in sources:
            source_id = obs.obs_source_get_unversioned_id(source)
            if source_id == "ffmpeg_source":
                name = obs.obs_source_get_name(source)
                obs.obs_property_list_add_string(p,name,name)
        obs.source_list_release(sources)
    return properties