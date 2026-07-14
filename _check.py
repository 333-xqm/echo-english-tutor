import json, re
with open('D:/11111/english-tutor-app/server.py','r',encoding='utf-8') as f: s=f.read()
with open('D:/11111/english-tutor-app/static/index.html','r',encoding='utf-8') as f: h=f.read()
checks = [
  ('BE-1','/api/log_answer endpoint','@app.post("/api/log_answer")' in s),
  ('BE-2','/api/stats endpoint','@app.get("/api/stats")' in s),
  ('BE-3','/api/quiz endpoint','@app.post("/api/quiz")' in s),
  ('BE-4','QUESTION_BANK defined','QUESTION_BANK' in s),
  ('BE-5','Adaptive: stage down (<40%)','mastery < 0.4' in s),
  ('BE-6','Adaptive: stage up (>80%)','mastery > 0.8' in s),
  ('BE-7','threading.Lock','threading.Lock()' in s),
  ('BE-8','stage_mastery dict','stage_mastery' in s),
  ('FE-1','.quiz-card CSS','.quiz-card{' in ''.join(h.split())),
  ('FE-2','.quiz-opt-item CSS','.quiz-opt-item{' in ''.join(h.split())),
  ('FE-3','.quiz-fb CSS','.quiz-fb{' in ''.join(h.split())),
  ('FE-4','.stats-bar CSS','.stats-bar{' in ''.join(h.split())),
  ('FE-5','fetchQuiz() JS','fetchQuiz' in h),
  ('FE-6','checkAnswer() JS','checkAnswer' in h),
  ('FE-7','refreshStats() JS','refreshStats' in h),
  ('FE-8','Stats bar elements','statAnswers' in h and 'statRate' in h and 'statWrong' in h),
  ('FE-9','send() wrap for refresh','origSend = send' in h),
  ('BUG-1','checkAnswer always sends correct:true','correct:true' in h),
  ('BUG-2','addMessage used but function is addMsg','addMessage' in h and 'addMsg' in h),
  ('MISS-1','Dedicated quiz button in quick-reply','u505au9053u9898' in h or 'u505au9898' in h or 'quiz-btn' in h),
  ('MISS-2','Feedback visible class (.sh)','quiz-fb.sh' in ''.join(h.split())),
  ('OK-1','refreshStats -> updateProgress','updateProgress(d.current_stage)' in h),
]
for cid,name,ok in checks:
  print(('\u2705' if ok else '\u274c') + ' ' + cid + ' ' + name)
