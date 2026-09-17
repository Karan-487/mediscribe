from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import sqlite3, re

BASE = Path(__file__).parent
DB = BASE / 'mediscribe.db'
app = FastAPI(title='MediScribe v1')

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS doctors (doctor_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, specialty TEXT);
    CREATE TABLE IF NOT EXISTS patients (patient_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, age INTEGER, gender TEXT, phone TEXT);
    CREATE TABLE IF NOT EXISTS consultations (consultation_id INTEGER PRIMARY KEY AUTOINCREMENT, doctor_id INTEGER, patient_id INTEGER NOT NULL, date_time TEXT DEFAULT CURRENT_TIMESTAMP, transcript TEXT, clinical_note TEXT, status TEXT, FOREIGN KEY(doctor_id) REFERENCES doctors(doctor_id), FOREIGN KEY(patient_id) REFERENCES patients(patient_id));
    ''')
    if c.execute('SELECT COUNT(*) FROM doctors').fetchone()[0] == 0:
        c.execute("INSERT INTO doctors(name,email,password,specialty) VALUES(?,?,?,?)", ('Dr. Karan','doctor@mediscribe.com','demo','General Medicine'))
    if c.execute('SELECT COUNT(*) FROM patients').fetchone()[0] == 0:
        c.executemany('INSERT INTO patients(name,age,gender,phone) VALUES(?,?,?,?)', [
            ('Rahul Sharma',24,'Male','9876543210'), ('Priya Kaur',31,'Female','9876501234'), ('Aman Singh',28,'Male','9811122233'), ('Simran Gill',42,'Female','9812345678')])
        c.executemany('INSERT INTO consultations(doctor_id,patient_id,transcript,clinical_note,status) VALUES(?,?,?,?,?)', [
            (1,1,'Patient reports mild headache and fever for 2 days.','CHIEF COMPLAINT\nHeadache and fever\n\nSYMPTOMS\n• Fever\n• Headache\n\nDURATION\n2 days\n\nASSESSMENT\nPossible viral infection\n\nPLAN\nRest, hydration and follow-up as clinically appropriate.','Completed'),
            (1,2,'Patient reports cough and fatigue for 5 days. No vomiting.','CHIEF COMPLAINT\nCough and fatigue\n\nSYMPTOMS\n• Cough\n• Fatigue\n\nDURATION\n5 days\n\nNEGATIVE SYMPTOMS\n• No vomiting\n\nASSESSMENT\nFurther clinical assessment required\n\nPLAN\nRest, hydration and follow-up as clinically appropriate.','Completed')])
    c.commit(); c.close()
init_db()

class Login(BaseModel): email: str; password: str
class PatientIn(BaseModel): name: str; age: int | None = None; gender: str | None = None; phone: str | None = None
class ConsultationIn(BaseModel): doctor_id: int = 1; patient_id: int; transcript: str

@app.get('/')
def home(): return FileResponse(BASE/'static'/'index.html')

@app.post('/api/login')
def login(x: Login):
    c=db(); r=c.execute('SELECT doctor_id,name,email,specialty FROM doctors WHERE email=? AND password=?',(x.email,x.password)).fetchone(); c.close()
    if not r: raise HTTPException(401,'Invalid credentials')
    return dict(r)

@app.get('/api/patients')
def patients():
    c=db(); rows=c.execute('SELECT p.*, COUNT(c.consultation_id) consultation_count FROM patients p LEFT JOIN consultations c ON p.patient_id=c.patient_id GROUP BY p.patient_id ORDER BY p.name').fetchall(); c.close(); return [dict(r) for r in rows]

@app.post('/api/patients')
def add_patient(x: PatientIn):
    c=db(); cur=c.execute('INSERT INTO patients(name,age,gender,phone) VALUES(?,?,?,?)',(x.name,x.age,x.gender,x.phone)); c.commit(); r=c.execute('SELECT * FROM patients WHERE patient_id=?',(cur.lastrowid,)).fetchone(); c.close(); return dict(r)

@app.get('/api/patients/{patient_id}')
def patient_detail(patient_id: int):
    c=db(); p=c.execute('SELECT * FROM patients WHERE patient_id=?',(patient_id,)).fetchone()
    if not p: c.close(); raise HTTPException(404,'Patient not found')
    rows=c.execute('SELECT consultation_id,date_time,transcript,clinical_note,status FROM consultations WHERE patient_id=? ORDER BY consultation_id DESC',(patient_id,)).fetchall(); c.close()
    return {'patient':dict(p),'consultations':[dict(r) for r in rows]}

@app.get('/api/consultations')
def consultations():
    c=db(); rows=c.execute('''SELECT c.*,p.name patient_name,p.age,p.gender FROM consultations c JOIN patients p ON p.patient_id=c.patient_id ORDER BY c.consultation_id DESC''').fetchall(); c.close(); return [dict(r) for r in rows]

def generate_note(t):
    s=t.lower(); symptoms=[]
    for word in ['fever','headache','fatigue','cough','nausea','vomiting','pain','dizziness','cold','sore throat','shortness of breath']:
        if word in s: symptoms.append(word.title())
    duration='Not specified'; m=re.search(r'(\d+)\s*(day|days|week|weeks|month|months)',s)
    if m: duration=f"{m.group(1)} {m.group(2)}"
    negatives=[]
    for phrase,label in [('no vomiting','No vomiting'),('no chest pain','No chest pain'),('no cough','No cough'),('no fever','No fever')]:
        if phrase in s: negatives.append(label)
    complaint=' and '.join(symptoms[:2]) if symptoms else 'General complaint'
    if 'fever' in s and any(x in s for x in ['cough','cold','fatigue','sore throat']): assessment='Possible viral infection'
    elif symptoms: assessment='Further clinical assessment required'
    else: assessment='No specific assessment extracted'
    plan='Rest, hydration and follow-up as clinically appropriate.'
    out=f"CHIEF COMPLAINT\n{complaint}\n\nSYMPTOMS\n" + ('\n'.join('• '+x for x in symptoms) if symptoms else '• Not specified') + f"\n\nDURATION\n{duration}\n\n"
    if negatives: out += 'NEGATIVE SYMPTOMS\n'+'\n'.join('• '+x for x in negatives)+'\n\n'
    return out+f"ASSESSMENT\n{assessment}\n\nPLAN\n{plan}"

@app.post('/api/generate-note')
def generate_preview(x: ConsultationIn):
    if not x.transcript.strip(): raise HTTPException(400,'Transcript is empty')
    return {'clinical_note':generate_note(x.transcript)}

@app.post('/api/consultations')
def create_consultation(x: ConsultationIn):
    if not x.transcript.strip(): raise HTTPException(400,'Transcript is empty')
    note=generate_note(x.transcript); c=db(); cur=c.execute('INSERT INTO consultations(doctor_id,patient_id,transcript,clinical_note,status) VALUES(?,?,?,?,?)',(x.doctor_id,x.patient_id,x.transcript,note,'Completed')); c.commit(); cid=cur.lastrowid; c.close()
    return {'consultation_id':cid,'clinical_note':note,'status':'Completed'}

app.mount('/static', StaticFiles(directory=BASE/'static'), name='static')
