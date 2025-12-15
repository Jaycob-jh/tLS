% run_fooof_single.m
% =========================================================================
% RULES / CONTRACT (ENGLISH)
% 1) Headless script: must run under `matlab -batch` (no GUI, no dialogs).
% 2) Required environment variables:
%      - BST_CODE      : Brainstorm code folder (added to MATLAB path)
%      - BST_DB        : Brainstorm database root folder (contains protocols)
%      - BST_PROTOCOL  : Protocol name (directory name under BST_DB)
%      - SFILE         : PSD sFile path (relative to protocol data/, e.g. subX/.../timefreq_psd_*.mat)
% 3) Optional environment variables:
%      - FOOOF_TAG     : Output comment tag for indexing (e.g., "pre-yeo7-FOOOF" / "post-yeo7-FOOOF")
% 4) Exit codes:
%      - 0 success
%      - 1 error (prints full stack trace)
% =========================================================================

try
    bstCode = getenv_req('BST_CODE');
    bstDB   = getenv_req('BST_DB');
    prot    = getenv_req('BST_PROTOCOL');
    sFile   = getenv_req('SFILE');

    addpath(bstCode);

    if ~brainstorm('status')
        brainstorm server local;
    end

    db_import(bstDB);
    iProt = bst_get('Protocol', prot);
    if isempty(iProt)
        error('Protocol "%s" not found under "%s".', prot, bstDB);
    end
    gui_brainstorm('SetCurrentProtocol', iProt);

    % Resolve/validate input file
    if ~strncmp(sFile,'link|',5) && exist(sFile,'file')
        try, sFile = file_short(sFile); catch, end
    end
    fp = file_fullpath(sFile);
    if ~exist(fp,'file')
        error('PSD missing in protocol "%s": %s (resolved: %s)', prot, sFile, fp);
    end

    if exist('process_fooof','file') ~= 2
        error(['process_fooof not found. Please ensure Brainstorm has the FOOOF/specparam process ' ...
               '(install/update via Brainstorm Plugins).']);
    end

    bst_report('Start', sFile);
    sOut = bst_process('CallProcess','process_fooof', sFile, [], ...
        'implementation','matlab', ...
        'freqrange',[1,40], ...
        'powerline','None', ...
        'method','leastsquare', ...
        'peakwidth',[0.5,12], ...
        'maxpeaks',3, ...
        'minpeakheight',3, ...
        'proxthresh',2, ...
        'apermode','fixed', ...
        'guessweight','none', ...
        'sorttype','param', ...
        'sortparam','frequency', ...
        'sortbands',{'delta','2, 4'; 'theta','5, 7'; 'alpha','8, 12'; ...
                     'beta','15, 29'; 'gamma1','30, 59'; 'gamma2','60, 90'});

    % Variable tag from env (default keeps script runnable without submit wrapper)
    tag = getenv_default('FOOOF_TAG', 'post-yeo7-FOOOF');
    sOut = bst_process('CallProcess','process_set_comment', sOut, [], ...
                       'tag', tag, 'isindex', 1);

    ReportFile = bst_report('Save', sOut);
    fprintf('Saved report: %s\n', ReportFile);

    exit(0);

catch ME
    disp(getReport(ME,'extended'));
    exit(1);
end


% ========================= helper functions ==============================
function v = getenv_req(name)
    v = getenv(name);
    if isempty(v), error('Env %s is empty.', name); end
end

function v = getenv_default(name, defaultVal)
    v = getenv(name);
    if isempty(v), v = defaultVal; end
end
