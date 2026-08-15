function harness()
h = eqd_matlb; set(h,'Visible','off');
hs = guidata(h);

% --- dump the two menu vocabularies (needed for the Python port) ---
s1 = get(hs.popupmenu1,'String'); s2 = get(hs.popupmenu2,'String');
fid = fopen('menus.json','w');
fprintf(fid,'%s', jsonencode(struct('oar',{cellstr(s1)},'tumor',{cellstr(s2)})));
fclose(fid);

cases = {
%  name          oar tum  d1   d2  nf2 ja2   d3  nf3 ja3   d4  nf4 ja4  bifrac
  'A_std2Gy',      2,  2, 2.0, 2.0, 25,  0,  0.0,  0,  0,  0.0,  0,  0, 0
  'B_hypo3Gy',     2,  2, 2.0, 3.0, 15,  0,  0.0,  0,  0,  0.0,  0,  0, 0
  'C_LQLtail',     2,  2, 2.0,10.0,  3,  0,  0.0,  0,  0,  0.0,  0,  0, 0
  'D_twophase',    2,  2, 2.0, 2.0, 25,  0,  1.8, 10,  7,  0.0,  0,  0, 0
  'E_nf90',        2,  2, 2.0, 2.0, 90,  0,  0.0,  0,  0,  0.0,  0,  0, 0
  'F_nf86',        2,  2, 2.0, 2.0, 86,  0,  0.0,  0,  0,  0.0,  0,  0, 0
  'G_bifrac',      2,  2, 2.0, 1.2, 40,  0,  0.0,  0,  0,  0.0,  0,  0, 1
  'H_spinalcord', 13,  2, 2.0, 2.0, 25,  0,  0.0,  0,  0,  0.0,  0,  0, 0
  'I_lung24',     24, 10, 2.0, 2.0, 30,  0,  0.0,  0,  0,  0.0,  0,  0, 0
  'J_gap',         2,  2, 2.0, 2.0, 20, 14,  2.0, 10,  0,  0.0,  0,  0, 0
};

res = struct([]);
for k = 1:size(cases,1)
    c = cases(k,:);
    hs = guidata(h);
    set(hs.popupmenu1,'Value',c{2}); eqd_matlb('popupmenu1_Callback',hs.popupmenu1,[],hs);
    hs = guidata(h);
    set(hs.popupmenu2,'Value',c{3}); eqd_matlb('popupmenu2_Callback',hs.popupmenu2,[],hs);
    hs = guidata(h);
    set(hs.edit5,'String',num2str(c{4},'%.10g'));
    set(hs.edit7,'String',num2str(c{5},'%.10g'));
    set(hs.edit8,'String',num2str(c{6},'%.10g'));
    set(hs.edit9,'String',num2str(c{7},'%.10g'));
    set(hs.edit10,'String',num2str(c{8},'%.10g'));
    set(hs.edit11,'String',num2str(c{9},'%.10g'));
    set(hs.edit12,'String',num2str(c{10},'%.10g'));
    set(hs.edit13,'String',num2str(c{11},'%.10g'));
    set(hs.edit14,'String',num2str(c{12},'%.10g'));
    set(hs.edit15,'String',num2str(c{13},'%.10g'));
    bif = c{14};
    set(hs.radiobutton1,'Value',~bif); set(hs.radiobutton2,'Value',bif);
    set(hs.radiobutton3,'Value',~bif); set(hs.radiobutton4,'Value',bif);
    set(hs.radiobutton5,'Value',~bif); set(hs.radiobutton6,'Value',bif);
    guidata(h,hs);
    % fire the edit callbacks so text5/text8/text11 (etalements) are filled
    for cb = {'edit7','edit8','edit9','edit10','edit11','edit12','edit13','edit14','edit15'}
        hs = guidata(h);
        eqd_matlb([cb{1} '_Callback'], hs.(cb{1}), [], hs);
    end
    hs = guidata(h);
    eqd_matlb('pushbutton4_Callback', hs.pushbutton4, [], hs);
    hs = guidata(h);

    r = struct('name',c{1});
    r.in = struct('oar',c{2},'tum',c{3},'d1',c{4},'d2',c{5},'nf2',c{6},'ja2',c{7}, ...
                  'd3',c{8},'nf3',c{9},'ja3',c{10},'d4',c{11},'nf4',c{12},'ja4',c{13},'bifrac',bif);
    for fn = {'bede1','eqds1','bedet1','eqdt1','bede2','eqds2','bedet2','eqdt2', ...
              'bede3','eqds3','bedet3','eqdt3','eqdtotal','eqdttotal', ...
              'text5','text8','text11','text104','text105','text106'}
        v = get(hs.(fn{1}),'String');
        if ~ischar(v), v = num2str(v,'%.15g'); end
        r.out.(fn{1}) = strtrim(v);
    end
    if isempty(res), res = r; else, res(end+1) = r; end %#ok<AGROW>
    fprintf('%-14s EQDs=%-18s EQDt=%-18s NTCP=%-10s K=%s\n', ...
        r.name, r.out.eqdtotal, r.out.eqdttotal, r.out.text104, r.out.text105);
end

fid = fopen('golden.json','w'); fprintf(fid,'%s', jsonencode(res)); fclose(fid);
fprintf('WROTE golden.json (%d cases)\n', numel(res));
close(h);
