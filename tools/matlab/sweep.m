function sweep()
C = build_cases();
n = size(C,1);
fprintf('CASES=%d\n', n);
h = eqd_matlb; set(h,'Visible','off');
fid = fopen('golden.jsonl','w');
lastO = -1; lastT = -1; t0 = tic;
OUT = {'bede1','eqds1','bedet1','eqdt1','bede2','eqds2','bedet2','eqdt2', ...
       'bede3','eqds3','bedet3','eqdt3','eqdtotal','eqdttotal', ...
       'text5','text8','text11','text104','text105','text106'};
for k = 1:n
    c = C(k,:);
    try
        hs = guidata(h);
        if c(1) ~= lastO
            set(hs.popupmenu1,'Value',c(1)); eqd_matlb('popupmenu1_Callback',hs.popupmenu1,[],hs);
            lastO = c(1); hs = guidata(h);
        end
        if c(2) ~= lastT
            set(hs.popupmenu2,'Value',c(2)); eqd_matlb('popupmenu2_Callback',hs.popupmenu2,[],hs);
            lastT = c(2); hs = guidata(h);
        end
        set(hs.popupmenu1,'Value',c(1)); set(hs.popupmenu2,'Value',c(2));
        E = {'edit5','edit7','edit8','edit9','edit10','edit11','edit12','edit13','edit14','edit15'};
        for j = 1:10, set(hs.(E{j}),'String',num2str(c(2+j),'%.10g')); end
        b = c(13);
        set(hs.radiobutton1,'Value',~b); set(hs.radiobutton2,'Value',b);
        set(hs.radiobutton3,'Value',~b); set(hs.radiobutton4,'Value',b);
        set(hs.radiobutton5,'Value',~b); set(hs.radiobutton6,'Value',b);
        guidata(h,hs);
        for cb = {'edit7','edit8','edit9','edit10','edit11','edit12','edit13','edit14','edit15'}
            hs = guidata(h); eqd_matlb([cb{1} '_Callback'], hs.(cb{1}), [], hs);
        end
        hs = guidata(h);
        eqd_matlb('pushbutton4_Callback', hs.pushbutton4, [], hs);
        hs = guidata(h);
        r = struct();
        r.in = struct('oar',c(1),'tum',c(2),'d1',c(3),'d2',c(4),'nf2',c(5),'ja2',c(6), ...
                      'd3',c(7),'nf3',c(8),'ja3',c(9),'d4',c(10),'nf4',c(11),'ja4',c(12),'bifrac',b);
        for j = 1:numel(OUT)
            v = get(hs.(OUT{j}),'String');
            if ~ischar(v), v = num2str(v,'%.15g'); end
            r.out.(OUT{j}) = strtrim(v);
        end
        fprintf(fid, '%s\n', jsonencode(r));
    catch ME
        fprintf(fid, '%s\n', jsonencode(struct('in', c, 'error', ME.message)));
    end
    if mod(k,100) == 0
        el = toc(t0);
        fprintf('%6d/%6d  %.3f s/case  ETA %.1f min\n', k, n, el/k, (n-k)*el/k/60);
    end
end
fclose(fid); close(h);
fprintf('DONE %d cases in %.1f min\n', n, toc(t0)/60);

function C = build_cases()
C = [];
% (1) every OAR x tumour pair on the reference 25 x 2 Gy schedule
for o = 2:35
    for t = 2:20
        C(end+1,:) = [o t 2 2 25 0 0 0 0 0 0 0 0]; %#ok<AGROW>
    end
end
% (2) wide schedule grid on two representative pairs
pairs = [2 2; 24 17];
doses = [1.2 1.5 1.8 2 2.5 3 4 5 6 8 10 12 15 20];
nfs   = [1 2 3 5 10 15 20 25 30 33 35 40 50 70 85 86 87 90 100];
gaps  = [0 7 14];
for p = 1:size(pairs,1)
    for d = doses
        for nn = nfs
            for g = gaps
                for b = 0:1
                    C(end+1,:) = [pairs(p,1) pairs(p,2) 2 d nn g 0 0 0 0 0 0 b]; %#ok<AGROW>
                end
            end
        end
    end
end
% (3) randomised two- and three-phase schedules
rs = RandStream('mt19937ar','Seed',20260815);
dchoice = [1.2 1.5 1.8 2 2.5 3 4 5 6 8 10];
for k = 1:600
    o = randi(rs,[2 35]); t = randi(rs,[2 20]);
    d1 = 2;
    d2 = dchoice(randi(rs,[1 numel(dchoice)])); n2 = randi(rs,[1 40]); g2 = randi(rs,[0 21]);
    d3 = dchoice(randi(rs,[1 numel(dchoice)])); n3 = randi(rs,[0 25]); g3 = randi(rs,[0 21]);
    if rand(rs) < 0.5
        d4 = dchoice(randi(rs,[1 numel(dchoice)])); n4 = randi(rs,[0 15]); g4 = randi(rs,[0 21]);
    else
        d4 = 0; n4 = 0; g4 = 0;
    end
    C(end+1,:) = [o t d1 d2 n2 g2 d3 n3 g3 d4 n4 g4 double(rand(rs)<0.3)]; %#ok<AGROW>
end
