"""Experimental Corkscrew controller; uses the original TORCS physics and damage.

The circuit model is read from the installed track XML. This is for local
development; eligibility of a static map in competition remains unverified.
"""
import bisect,importlib.util,math,os,xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(os.environ['TORCS_HOME']).expanduser().resolve()
P=Path(__file__).resolve().with_name('controller_v3_4.py')
spec=importlib.util.spec_from_file_location('v34_base',P)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
params=dict(lateral_ms2=15.,tight_ms2=15.,wide_ms2=0.,lateral_zones=[],accel_ms2=6.,brake_ms2=7.,max_kmh=180.,preview_m=12.,tight_preview_m=12.,steer_ff=0.65,throttle_gain=7.,attack_gears=False,kinematic_gears=False)
segments=[];length=0.;profile=[]
_shift_time=-10.;_shift_dir=0
_abs_limit=1.;_abs_time=-10.

def configure(values):
    global profile
    params.update(values)
    profile=_build_profile()

def _segments():
    global length
    doc=ET.fromstring((ROOT/'tracks/road/corkscrew/corkscrew.xml').read_text().replace('&default-surfaces;',''))
    for s in doc.findall('./section[@name="Main Track"]/section[@name="Track Segments"]/section'):
        a={e.get('name'):e.get('val') for e in s if e.tag in ('attnum','attstr')}
        kind=a['type'];r=float(a.get('radius',0));rend=float(a.get('end radius',r))
        arc=math.radians(float(a.get('arc',0)))
        seglen=float(a['lg']) if kind=='str' else (r+rend)/2*arc
        steps=int(float(a.get('profil steps',1)))
        if a.get('profil','spline')!='spline':steps=1
        elif steps==1:
            steplen=float(a.get('profil steps length',8))
            steps=int(seglen/steplen)+1 if steplen else 1
        if r!=rend and steps>1:
            seglen=steps*arc/sum(1/(r+(rend-r)*i/(steps-1)) for i in range(steps))
        for j in range(steps):
            radius=r+(rend-r)*j/(steps-1) if steps>1 else r
            size=seglen/steps
            segments.append((length,length+size,kind,radius,radius))
            length+=size
_segments()
ends=[s[1] for s in segments]

def _curvature(d):
    d=d%length
    s=segments[min(bisect.bisect_right(ends,d),len(segments)-1)]
    if s[2]=='str':return 0.
    frac=max(0.,min(1.,(d-s[0])/(s[1]-s[0])))
    radius=s[3]+(s[4]-s[3])*frac
    return (1 if s[2]=='lft' else -1)/max(radius,1.)

def _line_state(d):
    offsets=params.get('line_offsets',[])
    if not offsets:return 0.,0.,0.
    ds=params['line_ds'];x=(d%length)/ds;i=int(x);t=x-i;n=len(offsets)
    ym,y0,y1,yp=(offsets[j%n] for j in (i-1,i,i+1,i+2))
    # Catmull-Rom gives continuous offset and slope between bounded knots.
    a=.5*(y1-ym);b=ym-2.5*y0+2*y1-.5*yp;c=.5*(yp-ym)+1.5*(y0-y1)
    scale=params.get('line_scale',1.)
    return scale*(y0+a*t+b*t*t+c*t*t*t),scale*(a+2*b*t+3*c*t*t)/ds,scale*(2*b+6*c*t)/ds**2

def _line_curvature(d):
    stored=params.get('path_curvatures',[])
    if stored:
        x=(d%length)/params['line_ds'];i=int(x);f=x-i
        return stored[i%len(stored)]*(1-f)+stored[(i+1)%len(stored)]*f
    y,dy,ddy=_line_state(d);k=_curvature(d)
    kp=(_curvature(d+.5)-_curvature(d-.5))
    q=1-k*y
    return (k*q*q+q*ddy+kp*y*dy+2*k*dy*dy)/max((q*q+dy*dy)**1.5,.01)

def _build_profile():
    ds=2.;n=math.ceil(length/ds)
    p=[]
    for i in range(n+1):
        d=min(i*ds,length-.001)
        # Use a three-point preview to avoid an abrupt speed target at a
        # segment edge. The strongest curvature is the binding one.
        path_curvature=_line_curvature if params.get('line_speed',False) else _curvature
        k=max(abs(path_curvature(d+j)) for j in (0.,2.,4.))
        tight=(2425.<=d<=2530.) or (3235.<=d<=3310.)
        lateral=params['tight_ms2'] if tight else params['lateral_ms2']
        if not tight and params['wide_ms2'] and k<1./60.:
            lateral=params['wide_ms2']
        for zone_start,zone_end,zone_lateral in params['lateral_zones']:
            if zone_start<=d<=zone_end:lateral=zone_lateral
        cap=min(params['max_kmh']/3.6,math.sqrt(lateral/max(k,1e-5)))
        # Local terrain caps participate in braking, before reaching a crest.
        for zone_start,zone_end,zone_kmh in params.get('speed_zones',[]):
            if zone_start<=d<=zone_end:cap=min(cap,zone_kmh/3.6)
        p.append(cap)
    # Braking and acceleration passes, including the standing start.
    for i in range(n-1,-1,-1):
        p[i]=min(p[i],math.sqrt(p[i+1]**2+2*params['brake_ms2']*ds))
    # The one-lap grid is 10 m before the timing line; the car accelerates
    # across that distance before distFromStart wraps to zero.
    p[0]=math.sqrt(2*params['accel_ms2']*10.)
    for i in range(1,n+1):
        p[i]=min(p[i],math.sqrt(p[i-1]**2+2*params['accel_ms2']*ds))
    return p
configure({})

def _planned_speed(d):
    i=min(max(int(d/2),0),len(profile)-2)
    f=d/2-i
    return (profile[i]*(1-f)+profile[i+1]*f)*3.6

def drive(client):
    global _shift_time,_shift_dir,_abs_limit,_abs_time
    s=client.S.d;r=client.R.d
    diagnostic=base.drive_v3_4(client)
    try:d=float(s.get('distFromStart',float('nan')))
    except (TypeError,ValueError):d=float('nan')
    if not math.isfinite(d) or d<0 or d>=length:
        r['accel']=0.;r['brake']=max(r.get('brake',0.),0.2)
        diagnostic.update(attack_reason='invalid_distance',attack_target_kmh=0.)
        return diagnostic
    if diagnostic.get('mode')=='RECOVERY':return diagnostic
    if diagnostic.get('sensor_invalid') or diagnostic.get('scalar_invalid'):
        r['accel']=0.;r['brake']=max(r.get('brake',0.),.2)
        return diagnostic
    speed=max(0.,float(s.get('speedX',0.)))
    angle=float(s.get('angle',0.));pos=float(s.get('trackPos',0.))
    line_y,line_dy,_=_line_state(d)
    line_heading=math.atan2(line_dy,1-_curvature(d)*line_y)
    headings=params.get('path_headings',[])
    if headings:
        x=(d%length)/params['line_ds'];i=int(x);f=x-i
        line_heading=headings[i%len(headings)]*(1-f)+headings[(i+1)%len(headings)]*f
    heading_error=angle+line_heading
    target=_planned_speed(d)
    # Existing emergency/sensor caps remain hard upper bounds. Normal V3.4
    # curvature and its chicane cap are superseded by the circuit plan.
    if diagnostic.get('sensor_invalid') or diagnostic.get('scalar_invalid'):
        target=min(target,30.)
    if abs(pos)>.80 or abs(heading_error)>.23 or abs(angle)>.38:
        target=min(target,35.)
    elif abs(pos)>.60:
        target*=max(.55,1.-1.5*(abs(pos)-.60))
    if float(s.get('damage',0.))>0:
        target=min(target,40.)
    # Path tracking combines V3.4 feedback with bounded preview curvature.
    preview=params['preview_m']+speed/3.6*.15
    if 2425.<=d<=2530. or 3235.<=d<=3310.:
        preview=params['tight_preview_m']+speed/3.6*.15
    k=.20*_line_curvature(d)+.55*_line_curvature(d+preview)+.25*_line_curvature(d+2*preview)
    ff=math.atan(2.95*k)/math.radians(21)
    is_tight=(2425.<=d<=2530.) or (3235.<=d<=3310.)
    hg=params.get('tight_heading_gain',params.get('heading_gain',1.75)) if is_tight else params.get('heading_gain',1.75)
    cg=params.get('tight_center_gain',params.get('center_gain',.38)) if is_tight else params.get('center_gain',.38)
    feedback=(angle+line_heading)*(hg+2.5/max(speed/3.6,1.))-(pos-line_y/6.)*cg
    steer=feedback+params['steer_ff']*ff
    ug=params.get('tight_understeer_gain',params.get('understeer_gain',0.)) if is_tight else params.get('understeer_gain',0.)
    steer+=ug*(speed/100.)**2*ff
    r['steer']=base._base.clip(steer,-1.,1.)
    error=target-speed
    r['accel']=base._base.clip(error/params['throttle_gain']+.18 if error>-.5 else 0.,0.,1.)
    r['brake']=base._base.clip(-error/7. if error<-.5 else 0.,0.,1.)
    if r['brake']>.02:r['accel']=0.
    wsv=s.get('wheelSpinVel',[])
    if isinstance(wsv,list) and len(wsv)>=4 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in wsv):
        lap_clock=float(s.get('curLapTime',0.))
        if lap_clock<_abs_time:_abs_limit=1.
        dt=max(.001,min(.1,lap_clock-_abs_time));_abs_time=lap_clock
        normal=abs(pos)<.8 and abs(heading_error)<.23 and abs(angle)<.38 and float(s.get('damage',0.))==0
        if r['brake']>.05 and speed>50 and normal and (2400<d<2530 or 3200<d<3300):
            slip=max(0.,1.-min(wsv[:2])*.3024/(speed/3.6))
            if slip>.20:_abs_limit=max(.05,_abs_limit-4.*dt)
            elif slip<.12:_abs_limit=min(1.,_abs_limit+2.*dt)
            r['brake']*=_abs_limit
            diagnostic.update(abs_front_slip=round(slip,4),abs_brake_limit=round(_abs_limit,4))
        else:_abs_limit=1.
        demand=r['accel']
        r['accel'],reason,slip=base._tc_signed_linear(demand,wsv,speed/3.6,True)
        # More traction utilisation only with small heading/lateral error.
        straight=abs(_curvature(d))<1/120. and abs(_curvature(d+20))<1/120.
        aligned=abs(heading_error)<.07 and abs(angle)<.2 and abs(pos-line_y/6.)<.30 and abs(pos)<.55 and abs(float(s.get('speedY',0.)))<2.
        if straight and aligned and speed>25 and r['brake']<.02 and not diagnostic.get('safety_reason'):
            velocity=speed/3.6
            onset=max(1.5,velocity*params.get('straight_tc_onset',.05))
            span=max(3.,velocity*params.get('straight_tc_span',.10))
            rear=(wsv[2]+wsv[3])*.5*base.REAR_RADIUS
            excess=max(0.,rear-velocity-onset)
            r['accel']=demand*max(0.,1.-excess/span)
            diagnostic.update(attack_tc='straight_slip_budget',attack_tc_slip=rear-velocity)
        elif params.get('exit_tc',False) and error>15 and abs(pos)<params.get('exit_pos_gate',.4) and abs(heading_error)<params.get('exit_angle_gate',.08) and abs(angle)<.2 and abs(float(s.get('speedY',0.)))<params.get('exit_lateral_gate',3.) and abs(_line_curvature(d))<1/params.get('exit_radius_gate',70.) and speed>65 and r['brake']<.02 and not diagnostic.get('safety_reason'):
            velocity=speed/3.6;rear=(wsv[2]+wsv[3])*.5*base.REAR_RADIUS
            r['accel']=demand*max(0.,1.-max(0.,rear-velocity-(params.get('exit_slip_base',1.)+params.get('exit_slip_ratio',.02)*velocity))/params.get('exit_slip_span',3.))
            diagnostic.update(attack_tc='aligned_exit_budget',attack_tc_slip=rear-velocity)
    else:r['accel']=0.
    if params['attack_gears'] and s.get('gear',0)>0:
        lap_time=float(s.get('curLapTime',0.))
        if lap_time<_shift_time:_shift_time=lap_time-10.;_shift_dir=0
        gear=int(s['gear'])
        valid=isinstance(wsv,list) and len(wsv)>=4 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in wsv)
        if valid:
            choice=base._select_gear_v321(gear,float(s['rpm']),speed,r['accel'],r['brake'],wsv,abs(float(s.get('speedY',0.)))/3.6,pos,angle,bool(diagnostic.get('safety_reason')),lap_time,_shift_time,_shift_dir,True)
            r['gear']=choice[0]
            if params['kinematic_gears']:
                r['gear']=gear
                rear_slip=abs((wsv[2]+wsv[3])*.5*base.REAR_RADIUS-speed/3.6)
                stable=abs(pos)<.6 and abs(angle)<.18 and abs(float(s.get('speedY',0.)))/3.6<base.LAT_SPEED_GATE and rear_slip<base.SHIFT_SLIP_GATE
                if stable and lap_time-_shift_time>=base.SHIFT_DWELL_S and r['accel']>.4 and r['brake']<.02:
                    candidates=[]
                    for g in range(max(1,gear-1),min(6,gear+1)+1):
                        rpm=max(base.IDLE_PHYS,base._kinematic_phys_rpm(speed,g))
                        if rpm<base.LIMITER_PHYS-base.LIMITER_MARGIN:
                            candidates.append((base._wheel_torque(rpm,g,1.),g))
                    if candidates:
                        best_torque,best_gear=max(candidates)
                        current=base._wheel_torque(max(base.IDLE_PHYS,base._kinematic_phys_rpm(speed,gear)),gear,1.)
                        if best_torque>current*1.05 or base._kinematic_phys_rpm(speed,gear)>=base.LIMITER_PHYS-base.LIMITER_MARGIN:
                            r['gear']=best_gear
                    diagnostic['attack_kinematic_gear']=r['gear']
                elif choice[1]=='limiter_relief':r['gear']=choice[0]
            # A safe upshift near the limiter may relieve controlled wheel slip.
            force_up=False
            if params.get('slip_upshift',False) and straight and aligned and gear<6 and lap_time-_shift_time>=base.SHIFT_DWELL_S and r['accel']>.4 and r['brake']<.02:
                rpm=float(s['rpm'])/base.RPM_SCALE
                if rpm>base.LIMITER_PHYS*.95 and abs(rear_slip)<speed/3.6*.15:
                    r['gear']=gear+1;force_up=True
            brake_down=False
            if params.get('brake_downshift',False) and r['gear']==gear and gear>1 and r['brake']>.4 and abs(_curvature(d))<1/70. and abs(pos)<.3 and abs(angle)<.08 and rear_slip<3. and lap_time-_shift_time>=base.SHIFT_DWELL_S and not diagnostic.get('safety_reason'):
                predicted=max(base._kinematic_phys_rpm(speed,gear-1),float(s['rpm'])/base.RPM_SCALE*base.GEAR_RATIOS[gear-1]/base.GEAR_RATIOS[gear])
                if predicted<base.LIMITER_PHYS*.85:
                    r['gear']=gear-1;brake_down=True
                    diagnostic['attack_brake_downshift']=True
            # Select the slow-corner gear while braking, rather than waiting
            # for high throttle and low wheel slip on the corner exit.
            slow_corner=(2400.<d<2530.) or (3200.<d<3330.)
            corner_stable=abs(pos)<.65 and abs(heading_error)<.15 and abs(angle)<.35 and rear_slip<3. and not diagnostic.get('safety_reason')
            if slow_corner and corner_stable and gear>2 and speed<135. and r['brake']>.1 and lap_time-_shift_time>=base.SHIFT_DWELL_S:
                predicted=max(base._kinematic_phys_rpm(speed,gear-1),float(s['rpm'])/base.RPM_SCALE*base.GEAR_RATIOS[gear-1]/base.GEAR_RATIOS[gear])
                if predicted<base.LIMITER_PHYS*.90:
                    r['gear']=gear-1;brake_down=True
                    diagnostic['corner_preselect']=True
            # Keep second through the slow apex to avoid first-gear wheelspin.
            if slow_corner and speed<110. and gear==2 and r['gear']==1 and not diagnostic.get('safety_reason'):
                r['gear']=2
            if r['gear']!=gear:_shift_time=lap_time;_shift_dir=-1 if brake_down else (1 if force_up else choice[-1])
            diagnostic.update(attack_shift_reason=choice[1])
    diagnostic.update(attack_target_kmh=round(target,2),attack_curvature=round(k,5),attack_ff=round(ff,3),line_offset_m=round(line_y,3),line_heading=round(line_heading,4))
    return diagnostic
