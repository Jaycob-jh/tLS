% run_psd_single.m -- headless Brainstorm Welch PSD for ONE sFile
% =========================================================================
% RULES / CONTRACT (ENGLISH)
% 1) This script is NON-INTERACTIVE (headless). It must run under `matlab -batch`.
% 2) Required environment variables:
%      - BST_CODE      : Brainstorm code folder (added to MATLAB path)
%      - BST_DB        : Brainstorm database root folder (contains protocols)
%      - BST_PROTOCOL  : Protocol name (directory name under BST_DB)
%      - SFILE         : Brainstorm input file reference (e.g., "link|..." or relative path)
% 3) Optional environment variables:
%      - BST_SCOUTS_TXT : Path to a text file (one scout name per line; # comments allowed)
% 4) Exit codes:
%      - 0 on success
%      - 1 on any error (prints full stack trace)
% 5) This script MUST NOT open any GUI windows or require user interaction.
% =========================================================================

try
    % ===== 输入来自 sbatch 环境变量 =====
    bstCode = getenv('BST_CODE');
    bstDB   = getenv('BST_DB');
    sFile   = getenv('SFILE');
    prot    = getenv('BST_PROTOCOL');

    if isempty(sFile),  error('Env SFILE is empty.');  end
    if isempty(bstCode),error('Env BST_CODE is empty.');end
    addpath(bstCode);

    % ===== 以完全无界面模式启动；首次启动避免交互 =====
    if ~brainstorm('status')
        brainstorm server local;
    end

    % ===== 正确加载你的数据库根 + 选择协议（官方推荐）=====
    if isempty(bstDB), error('Env BST_DB is empty.'); end
    db_import(bstDB);
    if isempty(prot), error('Env BST_PROTOCOL is empty.'); end
    iProt = bst_get('Protocol', prot);
    if isempty(iProt)
        error('Protocol "%s" not found under "%s".', prot, bstDB);
    end
    gui_brainstorm('SetCurrentProtocol', iProt);

    % ===== 健壮性检查：当前协议必须有效，且能解析 sFile =====
    Pinfo = bst_get('ProtocolInfo');
    assert(isstruct(Pinfo) && ~isempty(Pinfo.STUDIES), 'No current protocol selected.');

    if ~strncmp(sFile,'link|',5) && contains(sFile, filesep) && exist(sFile,'file')
        try sFile = file_short(sFile); catch, end
    end
    fp = file_fullpath(sFile);
    if ~exist(fp,'file')
        error('Input not found in protocol "%s": %s\nResolved: %s', prot, sFile, fp);
    end

    % ===== Load scouts list (externalized, but KEEP atlas string EXACTLY) =====
    scoutsTxt = getenv('BST_SCOUTS_TXT');
    if isempty(scoutsTxt)
        scoutsTxt = fullfile(fileparts(mfilename('fullpath')), 'schaefer2018_100_7net_scouts.txt');
    end
    scoutNames = read_scout_list(scoutsTxt);

    % ===== 开始流程 =====
    bst_report('Start', sFile);

    sOut = bst_process('CallProcess','process_psd', sFile, [], ...
        'timewindow',[0,720], ...
        'win_length',1, ...
        'win_overlap',50, ...
        'units','physical', ...
        'clusters', {'From volume: Schaefer2018_100_7net', scoutNames}, ...
        'scoutfunc', 1, ...
        'win_std', 0, ...
        'edit', struct('Comment','Scouts,Power','TimeBands',[], 'Freqs',[], ...
                       'ClusterFuncTime','after','Measure','power', ...
                       'Output','all','SaveKernel',0));

    sOut = bst_process('CallProcess','process_set_comment', sOut, [], ...
                       'tag','pre-s100-PSD','isindex',1);

    ReportFile = bst_report('Save', sOut);
    fprintf('Saved report: %s\n', ReportFile);

catch ME
    disp(getReport(ME,'extended'));
    exit(1);
end
exit(0);


% ========================= helper functions ==============================
function scouts = read_scout_list(txtFile)
    if ~exist(txtFile,'file')
        error('Scouts list file not found: %s', txtFile);
    end
    fid = fopen(txtFile,'r');
    if fid < 0, error('Cannot open scouts list file: %s', txtFile); end
    C = textscan(fid, '%s', 'Delimiter','\n', 'Whitespace','');
    fclose(fid);

    lines = strtrim(C{1});
    lines(cellfun(@isempty, lines)) = [];
    lines(startsWith(lines,'#')) = [];
    scouts = lines(:)';   % 1xN cellstr
end
