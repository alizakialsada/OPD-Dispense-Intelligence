const CONFIG = {
  gmailLabel: 'Dispense Update',
  senderContains: '',
  subjectContains: '',
  githubOwner: 'YOUR_GITHUB_USERNAME',
  githubRepo: 'OPD-Dispense-Intelligence',
  githubBranch: 'main',
  incomingFileName: 'medica-latest.xlsx'
};

function importLatestMedicaAttachment() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Set GITHUB_TOKEN in Script Properties.');
  const label = GmailApp.getUserLabelByName(CONFIG.gmailLabel);
  if (!label) throw new Error('Gmail label not found: ' + CONFIG.gmailLabel);
  const threads = label.getThreads(0, 20);
  let newest = null;
  threads.forEach(t => t.getMessages().forEach(m => {
    if (CONFIG.senderContains && !m.getFrom().toLowerCase().includes(CONFIG.senderContains.toLowerCase())) return;
    if (CONFIG.subjectContains && !m.getSubject().toLowerCase().includes(CONFIG.subjectContains.toLowerCase())) return;
    m.getAttachments().forEach(a => {
      if (/\.xlsx$/i.test(a.getName()) && (!newest || m.getDate() > newest.date)) newest = {date:m.getDate(), blob:a.copyBlob(), message:m};
    });
  }));
  if (!newest) throw new Error('No matching Excel attachment found.');
  const props = PropertiesService.getScriptProperties();
  const fingerprint = newest.date.toISOString() + '|' + newest.blob.getName() + '|' + newest.blob.getBytes().length;
  if (props.getProperty('LAST_ATTACHMENT') === fingerprint) return;
  putGithubFile_('incoming/' + CONFIG.incomingFileName, newest.blob.getBytes(), token, 'Automated Medica Cloud update');
  props.setProperty('LAST_ATTACHMENT', fingerprint);
}

function putGithubFile_(path, bytes, token, message) {
  const base = `https://api.github.com/repos/${CONFIG.githubOwner}/${CONFIG.githubRepo}/contents/${path}`;
  let sha = null;
  const get = UrlFetchApp.fetch(base + '?ref=' + encodeURIComponent(CONFIG.githubBranch), {muteHttpExceptions:true, headers:{Authorization:'Bearer ' + token, Accept:'application/vnd.github+json'}});
  if (get.getResponseCode() === 200) sha = JSON.parse(get.getContentText()).sha;
  const payload = {message, content:Utilities.base64Encode(bytes), branch:CONFIG.githubBranch};
  if (sha) payload.sha = sha;
  const res = UrlFetchApp.fetch(base, {method:'put', contentType:'application/json', payload:JSON.stringify(payload), muteHttpExceptions:true, headers:{Authorization:'Bearer ' + token, Accept:'application/vnd.github+json'}});
  if (res.getResponseCode() < 200 || res.getResponseCode() >= 300) throw new Error(res.getContentText());
}
