import numpy as np
import random

STATE_REST=0
STATE_PROCESS=1
STATE_LOAD=2
STATE_WASH=3
STATE_MOVE=4

class process_system(object):
    def __init__(self,t_move,t_process,tools,n_process,t_load,t_wash):
        self.t_move=t_move
        self.t_process=t_process
        self.t_load=t_load
        self.t_wash=t_wash
        self.tools=tools
        self.n_process=n_process
        
        self.timestep=1
        
        self.n_CNC=8
        self.t_move_CNC=np.array([[
            ([0]+self.t_move)[abs(i//2-j//2)]
        for j in range(self.n_CNC)] for i in range(self.n_CNC)])
        
        self.CNC=[machine_CNC(t_process=self.t_process[i],tool=self.tools[i],system=self) for i in range(self.n_CNC)]
        self.RGV=machine_RGV(t_move_CNC=self.t_move_CNC,t_load=self.t_load,t_wash=t_wash,system=self)
        self.n_sample=0
        self.samples=[]
        self.uncompleted_samples=[]

    def run(self,t_run):
        self.state=STATE_PROCESS
        for self.time in range(0,t_run,self.timestep):
            if self.RGV.state==STATE_REST:
                # Determine what to do
                states=[CNC.state for CNC in self.CNC]
                requirements=[i for i in range(len(states))
                                if (states[i] == STATE_REST) and (self.CNC[i].tool==0 or len(self.uncompleted_samples)>0) ]
                if requirements:
                    self.RGV.determine=self.determine(requirements)
                else:
                    self.RGV.determine=None
            
            # Last
            for CNC in self.CNC:
                CNC.last(self.timestep)
            self.RGV.last(self.timestep)
        
        # Unload all samples
        self.state=STATE_REST
        while any([CNC.sample is not None for CNC in self.CNC]):
            if self.RGV.state==STATE_REST:
                states=[CNC.sample is not None for CNC in self.CNC]
                requirements=[i for i in range(len(states)) if states[i]]
                if requirements:
                    self.RGV.determine=self.determine(requirements)
                else:
                    self.RGV.determine=None
            
            for CNC in self.CNC:
                CNC.last(self.timestep)
            self.RGV.last(self.timestep)
            self.time+=self.timestep
        if self.RGV.sample is not None:
            if self.RGV.sample.processstep>=self.n_process:
                self.samples.append(self.RGV.sample)
                        
    def determine(self,requirements):
        # Here is what we need to discuss
        move_time=[self.t_move_CNC[self.RGV.position][requirement]+self.t_load[requirement] for requirement in requirements]
        best=requirements[np.where(move_time==np.min(move_time))[0][0]]
        return best
        
class machine_CNC(object):
    def __init__(self,t_process,tool,system):
        self.t_process=t_process
        self.system=system
        self.tool=tool

        self.state=STATE_REST
        self.t_state=0
        self.t_statetotal=0
        self.sample=None
        self.determine=None

    def last(self,timestep):
        if not self.state==STATE_REST:
            self.t_state+=timestep
            if self.t_state>=self.t_statetotal:
                self.state=STATE_REST
                self.t_state=0
    
class machine_RGV(object):
    def __init__(self,t_move_CNC,t_load,t_wash,system):
        self.t_move_CNC=t_move_CNC
        self.t_load=t_load
        self.t_wash=t_wash
        self.system=system
        
        self.state=STATE_REST
        self.t_state=0
        self.t_statetotal=0
        self.sample=None
        self.unload_sample=None
        self.load_sample=None
        self.position=1
        self.determine=None

    def last(self,timestep):
        if not self.state==STATE_REST:
            self.t_state+=timestep
            if self.t_state>=self.t_statetotal:
                self.todo()
                self.t_state=0
        else:
            self.todo()
            
    def todo(self):
        if self.determine is not None:
            if self.state==STATE_REST:
                # move
                if self.t_move_CNC[self.position][self.determine]>0:
                    self.move(self.determine)
                else:
                    self.position=self.determine
                    self.load(self.determine)
            elif self.state==STATE_MOVE:
                self.position=self.determine
                self.load(self.determine)
            elif self.state==STATE_LOAD:
                self.load_complete(self.determine)
            elif self.state==STATE_WASH:
                self.state=STATE_REST
    
    def move(self,move_to):
        self.state=STATE_MOVE
        self.t_statetotal=self.t_move_CNC[self.position][move_to]

    def load(self,id):
        self.state=STATE_LOAD
        self.t_statetotal=self.t_load[id]
        if self.system.CNC[id].sample is not None:
            # unload
            self.unload_sample=self.system.CNC[id].sample
            self.unload_sample.endtime.append(self.system.time)
            self.system.CNC[id].sample=None
        if self.system.state==STATE_PROCESS:
            if self.system.CNC[id].tool==0:
                # new sample
                self.load_sample=Sample(id=self.system.n_sample)
                self.system.n_sample+=1
            else:
                # load from uncompleted samples
                self.load_sample=self.system.uncompleted_samples[0]
                del self.system.uncompleted_samples[0]
            self.load_sample.starttime.append(self.system.time)
        
    def load_complete(self,id):
        # load sample
        if self.load_sample is not None:
            self.system.CNC[id].sample=self.load_sample
            self.load_sample=None
            self.system.CNC[id].state=STATE_PROCESS
            self.system.CNC[id].t_statetotal=self.system.CNC[id].t_process
            self.system.CNC[id].sample.CNCid.append(id)
        # wash sample
        if self.unload_sample is not None:
            if self.sample is not None:
                # complete
                self.sample.processstep+=1
                if self.sample.processstep>=self.system.n_process:
                    # completed sample
                    self.system.samples.append(self.sample)
                else:
                    # uncompleted sample
                    self.system.uncompleted_samples.append(self.sample)
                self.sample=None
            
            self.sample=self.unload_sample
            self.unload_sample=None
            self.state=STATE_WASH
            self.t_statetotal=self.t_wash
        else:
            self.state=STATE_REST
 

class Sample(object):
    def __init__(self,id):
        self.id=id
        self.processstep=0
        self.CNCid=[]
        self.starttime=[]
        self.endtime=[]
    
if __name__=='__main__':
    # case 1 , group 1
    system=process_system(
        t_move=[20,33,46],
        t_process=[560]*8,
        tools=[0]*8,
        n_process=1,
        t_load=[28,31]*4,
        t_wash=25
    )
    system.run(8*60*60)
    with open("case1group1.txt",'w') as f:
        for sample in sorted(system.samples,key=lambda x:x.id):
            print(sample.id+1,sample.CNCid[0]+1,sample.starttime[0],sample.endtime[0],file=f)

    # case 1 , group 2
    system=process_system(
        t_move=[23,41,59],
        t_process=[580]*8,
        tools=[0]*8,
        n_process=1,
        t_load=[30,35]*4,
        t_wash=30
    )
    system.run(8*60*60)
    with open("case1group2.txt",'w') as f:
        for sample in sorted(system.samples,key=lambda x:x.id):
            print(sample.id+1,sample.CNCid[0]+1,sample.starttime[0],sample.endtime[0],file=f)     
            
    # case 1 , group 3
    system=process_system(
        t_move=[18,32,46],
        t_process=[545]*8,
        tools=[0]*8,
        n_process=1,
        t_load=[27,32]*4,
        t_wash=25
    )
    system.run(8*60*60)
    with open("case1group3.txt",'w') as f:
        for sample in sorted(system.samples,key=lambda x:x.id):
            print(sample.id+1,sample.CNCid[0]+1,sample.starttime[0],sample.endtime[0],file=f)     
            
    # case 2, group 1  
    system=process_system(
        t_move=[20,33,46],
        t_process=[400,378]*4,
        tools=[0,1]*4,
        n_process=2,
        t_load=[28,31]*4,
        t_wash=25
    )
    system.run(8*60*60)
    with open("case2group1.txt",'w') as f:
        for sample in sorted(system.samples,key=lambda x:x.id):
            print(sample.id+1,sample.CNCid[0]+1,sample.starttime[0],sample.endtime[0],sample.CNCid[1]+1,sample.starttime[1],sample.endtime[1],file=f)
    
    # case 2, group 2
    system=process_system(
        t_move=[23,41,59],
        t_process=[280,280,500,500,500,500,500,280],
        tools=[0,0,1,1,1,1,1,0],
        n_process=2,
        t_load=[30,35]*4,
        t_wash=30
    )
    system.run(8*60*60)
    with open("case2group2.txt",'w') as f:
        for sample in sorted(system.samples,key=lambda x:x.id):
            print(sample.id+1,sample.CNCid[0]+1,sample.starttime[0],sample.endtime[0],sample.CNCid[1]+1,sample.starttime[1],sample.endtime[1],file=f)
    
    # case 2, group 3
    system=process_system(
        t_move=[18,32,46],
        t_process=[455,455,182,182,182,455,455,455],
        tools=[0,0,1,1,1,0,0,0],
        n_process=2,
        t_load=[27,32]*4,
        t_wash=25
    )
    system.run(8*60*60)
    with open("case2group3.txt",'w') as f:
        for sample in sorted(system.samples,key=lambda x:x.id):
            print(sample.id+1,sample.CNCid[0]+1,sample.starttime[0],sample.endtime[0],sample.CNCid[1]+1,sample.starttime[1],sample.endtime[1],file=f)
        