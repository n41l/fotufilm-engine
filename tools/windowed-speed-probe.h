#pragma once
extern "C" double wf_speed_clock();
extern "C" bool wf_speed_initialize(bool);
extern "C" void wf_speed_begin(int);
extern "C" bool wf_speed_finish(const char *,double,double);
