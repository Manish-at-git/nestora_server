"""Create the legacy Nestora domain tables in a fresh server database.

This static snapshot was captured during the migration effort.  Alembic never
connects to the legacy database.  The four tables already owned by the clean
server (accounts, roles, features, and role_feature_permissions) are excluded
so cookie-session authentication and the RBAC seed remain intact.
"""

import base64
import gzip
import json

from alembic import op


revision = "20260919_0003"
down_revision = "20260919_0002"
branch_labels = None
depends_on = None


# The 80 missing source-table definitions are gzip-compressed JSON so this migration
# remains self-contained without depending on nestora_backup_2 at runtime.
_COMPRESSED_LEGACY_TABLES = (
    "ABzY8000000{`7T+j85ulE0$Li<v6dmgAi4p53bR;Bh=Nsm(Z9$9XulXN!hNNWz#TI3OuUXKVj`0q_P8S4og8&5JFGO<eni?nd{2"
    "|L>au<nYaZya7dln<9ZZEb8jb<(o9k=&!dAcQ=oBv&WmCKHtrrB$%gJ^p9dTdqU~cELi~(z5my@v->ZPv-|I#KVR}kHL5fCG+P70"
    "0j{sErVw+SZk}c}{83LHB%p>%Oz1;cG<kHfgasrZySTi_0V--(06Gr(ts(SDO+O?sgL49Ego}%}vyXQ_-+cf4I2+&Nt(K@LARTXw"
    "iVbZgdM7|$bubBmwC^;YZ-jaEP{IH^Fi=0uQu?VzIUK-lzdt<O-9N^UpMJah_IUH#*Y=&JOt*Mv_T_%|{p&}z{)YBIRpA8jImgmA"
    "sKW(KiXdIGaW~$v-56&7E6yQ)p=(uj%K+*cBrCSlaYHg;6F+>=wEy+t({DEqf1my5-QQ;sLy5QlDBjNQ?tl4ofA_af6m35KG*0x_"
    "n}=_AkAG|G#b5LJUuL&oK7Xc@?7zoX|9*890~9Cd&Hr7F_(>;F#~EH4k#hj>z)U(VRBvL|_GCr0aF&)p!j^w*<b%=%{kd2|I;!6*"
    "TxhnYgk*t9eh`#9{JzXFAZeW7JV$j6VNAzg8+J$s>akZ-EEiW=vzi!ZalI*_7ofYn3Kl6OF7nD@Re>dJS=lZG6lQbz&+Mx>>`3_1"
    "Lfn42|MvKB^XdLkzbP@AFP`IfPqUxDJluWy<-Y4dXlC|s_wyYc((T<hMgj>H3tS@fpIacxz&_r6zGDpR=G*Pf$GgzTm*5n}1pd*$"
    "$|$rX7!P!t@C22fA(cRx6(Yd}-TOMGl4}mh2>M=utZGm<RWIa9y1=MdQfUUtlHfH==|=*8hY7_DQK}7q?PRK|fou;`N!XqZ3*igO"
    "IJaR3hvz;j2aetQQ#Et8rW2YpX(lJVa%F}$lxktxB%DJUmv9Q`BP9EmY%qO$aR%2gvkKD`E(x^L)&jvSjqxI`>V~bq1gfGlDk>_U"
    "8(9KtH<K~Bra)_|;820?<i?aPNgcC&cF6}yiC%C?LkN`x*`}QurCz%lx+EZVHk#pnGad6uVU-Y6wy*+HLsFv!V#@aMgw)}P;0INu"
    "xR&drf&nrR8T^jt@#M6ll^m=kt`evk%2b5pB`7vltVTuJR5fvvi8q?OVDcR2*o}B5`j~3Z+tLObfRi)~$Xq?6EUUy{Uf`TkyC-V@"
    "nMk2>5Wt`Zd9nBrM$u^0J$I^4AWaF?maUi_QpH*zQq{VXo`z0<FJw1~I70<win0S)B=BoDZb>4_Fa)MLx(8aK!bdNJIb?>EWD^ey"
    "tL~%MYnuJg$n7+y`YjdnK9q)wR(!Xdg#EROVFSP}_8L0I1<GJtqGWp`h)7!PvFrQ&r~mqX*PhRGL>1|N4bLN5lLiw&Mm8aUgg7yo"
    "w2xC{p$o)JiwI=&%vfS#JXR`jJ6JLdU}ZDUP_?2flT)f%*|=@n_e7h}sNPdctjcmZqH`qISYsQCmQ)=*PYcyD!*jY#Y}hqBTJ+`$"
    "!^WDx#r++)o3eMyY<dn?mzu)JB%^_$dR>#$4S`PfxFonKxz4nO#=<s+3Xr_y&tH9usE|Ub#qlsa-@)miuI=bsFcVhaqnorUdhR7$"
    "V7Eq`&-mry^5Qp`q9&&wenra_{dY@2sB)QIc=E<M)!Cn2dNV!H)*hO=U}5@F!h(+GJ2T|X9^e{5HrSi0Ld$|%n?4n@uLLidwnD!>"
    "zzS!r8R|B}m28A++Y;E2n?HcAqqxRS%>@-}ilS)QvdgN;b3i1E3{@cNH~~#1nOzf1&k{*ZPx^6hnjasQgl<-0cu3e}xh)|sa1E<H"
    "MOAQbPr`RV-`o)$F?1WAVO?e*fpJGk$f!x^fw$KwRI&?aFBjFaw%e%vAAIR3TD3<^iesh~lVE&wiqYV{J4e*GFHl7l8{p|H-G(gI"
    "h@QzE{uG;ML!7YeZ%}+2(pnmv8j{1}G`t!mWs@(Mo_Hunf>Z~oOB1qaAjgxvbcEJyI)xS~OnbijQ6k#(Ry?QeI5_Q8kgO5qB2=C&"
    "7KY`JU_5At!%g(H9V{9-o+FXKR2xLO!Zr3YD=E5(-2&lkP&uNz&gLb~*cvjWW`SJ667-zv2Pmr{H(Wqdt>Rl#F<%zfFn*#^;+Y<N"
    "Ccds7wjCTr_?TnmCirpRLp+EG6N%r#qkA(S^un0RPoun00fR_a4;!#SbLD5&Y!jCRG4px~6O@CDc5->GYh?og@rSMnJ8`FALuW}*"
    "O@ojX*X-6%kB;y55L{dY7%7u#&M5*HzL?bGP>VfUJtXcrq*CX{pp#q<!w8OYROO||9YQgv)s5p6=GcIBT38YB*yhM6wFa33qYkgT"
    "(z62L1Z$$E5x|3rGQ32E#_eu%@q?c8H5F%it%Pm;{A>IyvpyiQK0jG}AjT(7H4?uC-y(WGOEEF+Pxo|d7N@hYbjrfyfNyp+l#o=S"
    "56x&3SA7?nZ8F%)KiGx+$Yz(7`m)KbL8n<Hf_2Z}@e*8V9nR`TB@5)8P5^upCxl}ddk?FsMf#PRHx(+Ft3|W_ny@Xdx%qBFRzp&-"
    ")!OQ{&I#%Ey{<rAfwJ5VB?b?a5O_9mHVHc(&aY$_h9lfRQ5pLv6D24-Cr;p!>WFQm?^YC0L0|Bi#a_f)zQh!niW!W>-~v%c5%z9P"
    "Sp=9<6lygY!DHR}zvC5dNagHu)a^TFrd4{xxTli43$FhX|C<Ap@h8F<l<4U<>DoQ4+X>f0Qe~hK)x8gTb*}_nv;-u%`=~Rtp5mk#"
    "1207jUjbjZ$0kS20_s?UIVhfc^S_@zl)vE*IkfGEVf-Dms1h%V;?PZrq!?F2%S@P9!~rADghx=xzYol|CzZ)_R8$RNf%>+_0SgM_"
    "yOrQ_qco9r&Pc&utg<@oLtL+@GS}lmHGSMk7RE@J^Q1?`_m^5+C<$CZLN&Fxeb0e9{h`<on&KlM&k`dLU4>qvY%r~J&%v~<_EE<r"
    "^bd1TfTe_mcFiS)HRWPe{ChPC!|6JqtdOo4ZFmB3crBk>7%e(v_c+8kd20H(-ox~RQm?pmO%#qvMjzxT&`&w)KLy`E%Azx9^aXZL"
    "!<feBAOnSDc(@iN(Z$ujTwM)5t{27vON_WtSZjT#VA2rItx(|;V`^5i!JbOC$3|{pNblDCd`#%#O*MYG!Shzz0PBNZ;(Pm{Vb`nv"
    "CS2HyA<C#D<)_`8E!t%?Va&8g8Eq!l44?Ekv&{&u&kbiY^bEZamIEFcTMxpHngab1(^2vn>Cp00#lO99l&{?DA*j&(Szza=kQ(t)"
    "0108CJD@FJRIjIYDC^PEN0HNA8vXN!5PNwyJ*`IFg#hl)a;>A}0OQsQqxnGsr3W)3U~hM@sc7Qytu-rHO&`-?dbBH>Qw;Y0E;^bS"
    "ja;xcwLn?%Ncl;_P6dKDFjA!viJfVkms4&^c@>|-K?0$XJqX$_SV@SNc46xgW2Lu94`9QL>Exp6FDhR2OJ~4|>H88&Ok&TEg$zTy"
    "r{l1oz<Hp@@Xn4W0Pd7@;8oyLf;8kv`l@cXvL=Roms*iFU5xL2I*vXw3}%I@8k3D{zdNu%+pQA-x~vh-h}t2L`xUpnTbi@l^&F-M"
    "xb~a_1={iUA`uX;bC_;nv{t}2UI67_$-)KJv;)i%12idO|9i8x5>I~As~Y=a4qxDNz?;_iXA%nCQx8mO4QbZPKZ1R6!ZUC~61Tdp"
    "M8_RGP=q6ZFtbSbqHcb-ScY8}-jw!ywE7-t$E8?OTiziR&^z+frVp%O@*FcOvUhkIe*-u6@Svr~b?jxs4BZZeL-ko%)6op`jmFQy"
    "^Rdfl{H)@Ry4I#tHA5frd1DeF>}$9&^{W_e#<6c}wmFnys~oZ71*Q9jK<|Lk;RO%8RuAkG`PMe|I@ZMoO7mfx(U1319GQTZ;&>w!"
    "M#2%}x*2eEk0Y@WPaR`W@Kv0VGz?+SkHm1>>r$?4P7^2(l;ruJoXm_jN3qT;cw+?jjlv(_@Cy$d;XR}F*^M<_1YfH~;`Z7f>96w%"
    "R#ZIR;tQ-13=1C(A62TE?5D|!)W0v`s1&SwEJH!3pa`+gc1N`Y8AL;LrH%nPlP^=3w)^}!pu{cCOF9M?mE0jC3*=y7Jf49EhrI8<"
    "gT|@Zh*Q@-L7Jl?_VKwWfIW`2PxjA7u=lPF1G$`bDLU~cgNgL8lJ!}cy2+W>4`5ecns?W#BX2SZc>waR9SgN`SlH~|!}D+nEu5Y{"
    "_B&6Js=xmuhT-&_E3ik<8Zxm1ZuX04Ldg@vi>jiU40n5xCW96yuLKqjOBP%SD3Xo);@JW;Ssg2a&TwfgZFrzHi_Pv5s_4VAPXKKu"
    "i+fhsGYm<LZT5&2km1AOlRk1=!+m<d70y_GTPM6G%G=UvuQO>JJBC>9NpCEIdgU1e-1X_qF37#I$wm%)m>QDh&~ZbTf3zyNS6~D)"
    "KD_`Q%gyZBZbdSO>~UvRcFmoR_ZdnVLfB6gq-0%BvI4F!e%3reRow9wzst<JfC&Bdr~@XGcQhS13rTo}r)L9a%K4gf3H^9p3+b0s"
    "%9H_J6VJ?>b<+Qsyo}vilA>m;fMd*zDS6oOa!`fCyLKzi6XSfdnpxiojfE$i1T6<;N%3z%a2|J=-llUo53E%-@qF;Ny`f|(646~>"
    "I?UPgpoye*-PU%>XS9Dj9cvDmURzmfeRMG4b$Xk56p~!MwW@)c+*b9<+E9Y3zHnXBId0^IC&KxJ%C}~FVHT12%~U(2+vLOHuTQ^+"
    "2%-1s_r2n(5EkrIe8BCvYfwGg$(2KdBUUXvSX0w!i$>^^y*DNE$yfH~dGwT*Vrq4W+_Nm1r;-OU6fbblc^kGNuW~f`!Nd_b9vz(@"
    "2)$m1q)P8z6<#n|t&=I5)YW=2S4`>w4yJ~E2%(0_ykVr=D`&}y9h1lh*89eFJ|Eq0NT*=Ho#A;n)bWrJeZCK0|8x)UbKhQ{En0=+"
    "HV`i>t!gd#aAj^%9^<tcutNWY@$=l|-AG|c381}X;8-65Gfs;+PMgfRKrEla9A!Rbl|Yu^mpH{Q1q)KPJMnl`GY7qTB!cX7y~K04"
    "zyyxTBc~|@&ANcuy!#9{Ed8oa{7)AxDXjd}+mrM`jR{lEhAHu+-o|@e>tNMt4Z5gzc_l7_CK>#cib>uX{{CDAYJJ)4925nmX0L=Q"
    "EQPg@ER6Y=S+YgDb4Pk5g&<`&Zmk=VgCB7MO3>c9HKhDf>hH=q^|EYCU|Is?7~=v$Z|^rIOHfeJK>R8jjo?b;p}oL>c3xlmQYIHp"
    "Rz-OYC)GBr#*0-=UpaY3wP2UGZP67YK)|>P)~2S6g$7AIQEEw8K7W?w4yRU0`ufsrT+s6oXJXL=RKwh-xB`a@hcoJxQ+)}Q{mKp)"
    "<f&&aXv&{bG+d{5=ffkQaA(3}>lpJ=2-{ZPG$zX2sxVp=7j$83#Ii%~mQfvNESvC00v0v>|Fx?W95R1vXf1)|d}sL!%%`!7Z?G4T"
    "q0C<chDXCk(KsgJcO-pPd5l7bM>KsI`c@2J!yH3dzYHC#_Hc3Oq|S}CVUERSA!KN0<gVT06SIeR!}1g8l#^m29n1~Mgca@7q#-OR"
    "KLNX50O-eVJ+KcGL^*8T?b?t|0;Xm^L;C0jdW4y^T~bZ|*<FsZSCH-5eQL_}S7Q>|@YQ64vtg?u|1F_PJXNFmJ0bm&<)~;TwX#xF"
    "B~4ZFDqkf^#78v?^RC+zrTdfs3hd?(wlosHXgGbx6OPH?r7n-+*pRzaIJ&Svr&2HpXPL1?66Qsrcjw`nkXLq9%~f*Vzyfu~QiCO6"
    "n}an|9P=itQJGO;y27Sh;Dh$)m0Rk3EKNt^79y2!#5y7)5c<15hoFP@3d|;+WBhDUv!-A^q}si*$NAOw7)<-|EK9J$Im9o8{{FzW"
    "rWWzSQ@1eYP$i#ab;CJucZzNOr&g_uF%>Vht*>vOwHjGzS=jnW{N{bK+xarrh@vK<7e*r!p>U(lJ5{K*&%+<<^!>g+o2Wz<juCg|"
    "EZxCQ1EdGn5#F*Tc7fd4Xo1kw+C2PW!A4V)iA9qi#BiW-a*^=G76vq|uz_eMeMxvE2c>Nv3^eImAs%4{C!)x9*EeiNUlGJFZohxS"
    "3PhM+9@O+`&&oAy$CQN*BH@b$ErhX~@L_!2#8ZU3GspBVyD~${Kt5SR*ZZg9p5t_LjI8nFSflatZaKK+buy(0U28MH4ZeI|W}xfr"
    "9I|b<<F+M%7a)d`zv~mo?LG`5K)QBejz__hGfT<d4w_W!(vBn?;z$fh_DU@=KXY8<U^8dVsRGw=``h^5ct+`<Pu!-U)GX*i5ZbkQ"
    "ItU5y9XtvN2tAzx2}nMq6{tNt<qXUxrz>*=@1^Jym_W4N;xKSn5k5>P8b11}_8dZ*P9%M`yF}T7n{vGN12H-Vdp&m-f9Tlp0aSm_"
    "o|Ticv~DLzMGLTIE<@-ObTYtt(38s|=c2a*rG->&MVC7AFcOam1BRtBVE#e<@srN4gOlAsBc5`L=|%+%z{*Xx#9oIT8-pxziy7sl"
    "ca%U@b=GG~JIDZg+P35p&|oM{`I@p<8fzqdwWCD0T(2TrrM|CKDJRU~1f|>>!51Hd<ZuDd(HT#95b35tyGxx<#ON_GZ9ZR?S3x_W"
    "=itte0|l7TO|4nfRFOb?sF?uhXW8xFbL4FiPMc;Z-K8fpj&79&MLL-Kz8UIx-oSWR-tmYotXzOYy1IV`+7P;(kjEHoxMg6F(&;%I"
    "+gU7w%bqU5_@tg^@cWiwE$SncVI4*r4Ig*IJ!zRtndbW*r0wq`qqYe^IYU!AAGXbsJ_7Vu76O&_MVEdI0oc<x!NcRnnVHb}m~m;#"
    "uq}cFU_)(7G2<}DJZ>8Kjk1H?R70Xl@KO;4G8c$o&wRo;)EMN+wYdyqXVjNAKrBp>vG)2Z6-f5GpjOBHFvn>8tf|4kmdxajA6}C~"
    "Gx{uT$4WZ^GiEe3XDuHAd~A_y*Q|ztN>k5Gcg=x!x{)fj-QtE0gIru*{ERWXiuIME1<dG&FZGK4uBrT3f@0%Wd1UCZgruTu#OtLT"
    "&yjem<h}JCZ##=m1zUpISC&4Zf)yS8Ev0doP;{JudiD#&VgB1tDdOUmsi0ZLtBXuhJ%*||Rf6Q1nd-_FuCZUJ)Pc%q1?J8JLPo>K"
    "?TcfLBw(^R_f5-HR62&~E9R%&oIwpNF0|ITwyS^~z*hzA#P};KiQ_0tYGT-P24AAXE0IDs3U-ZCRyz{Zv|amqe+EixUyaUDDr*Y1"
    "lao#px$b{aMwPP~u|wh%Rb>V?l7Y&QYoeQy=JMmjn$^r>HKT~J+I&^xJl5S;_rBT~DAVBnVfvwO1)_o~D9p~307@wZcBm0nDHkFz"
    "-!3n8MH}VXV%NvGtE2Dw{eA-ZU=<>z;+AyAXj#|{b4K_Obx%X7<^i((nKCSVD!Qz{0dp$sQ#*AlVo)~iH43OI-CqY$RS#iih+PQ}"
    "WuVZR^nE1gz*f!8IFq2e3Pu>Do_F1cEt4bq<Yn~9d3cb-{S;sOP3Ir%gr`EEBBnDGN?{F<@gB7Z(qp;PtL;&G)tMMpUt)C<xvVLw"
    "s=9VeX?XTG)%lR=0+Fir%fXfbU&wB8Smp}In7HfKsR(}Uww_4W)ZZEN>ee2aNSGd(Iun_~9FirgOcf6s=40W~yyll~DP^^&@WP9S"
    ";iA1-wx3cV=8&iCi~ITwpmb=Q$(1Pa8X&<L40n2yS)i=2i%xc9nO_gf)-d8|_&8y-tlO;;0*Y_!spzYQa)AeiuT<>O-F27~ghx+m"
    "+;YD^QcvvHW1dx5`ivTrnEyA4DjCS*RMNk&$GN0zNQo=ElGS(Pv|hB#ixv0jUYT5#A95tG;R+=g^h{Au;7O()_@m?&{n$61(iXOh"
    "l2TOc!}5C*eU~}FW_0gO^B$lFiKi3h6bWAhmL+0RB!1iWye8wYf!T=dOJq5sje(Qtn%{-F9IQ5hqr8v;=RxJ;J9`9bGKS|iDDIqI"
    "<6z|p<jF_!_iaN#mDM*2L$MPHi=-M8zE%W7zn+1hlM{>pb@;r$AV=B8fzvWjfGai5qm}O1<e$M*&(1+s$J@OT+L!8s!SY&fbw}qF"
    "(Wo@n7A;{N0%d#*FHW?Y6A0azcGn<DPyt-=Edv}+$8KYf1=VX}5xOt^;NN}%NsShWd5+o>SB8t_s4oq*B&_3j4SX)m1x!y5iwTTD"
    "$!b8;Md~#b6I$zFJ@8!bCfH7;?{y?6zE9(8u01t>wIz+xtODV>l<RiuOS06~;)Zf6FQo{D`Qd@iCd&EAVB_E`WJ?rHPaqkb-4!+2"
    "*b`-cuXxzf9jgbU1TY=Dns<=HhlKQz^mW_ghnDUP3`Xi_S0=N~2u{;mH1YYml8~9eeVnM1SN~k;$aJ%dbieMBn9Q{5CNHR_SFJx("
    "h_Tr*M&SICm30i>Xoc$@A4w~f%J%4F&g8;oQ8k2Ln$qZbWs~TBehtO0U&V7#?s`op!%LTWmVx+Os1OB#&AfA<P~TwD%l*9lqnC%O"
    "aRUxouXs!sDpG#hKB!pSEK}g;v=ccl)1blovPpFSCmV45KmQN<TV|+E<p2N"
)


def _table_definitions() -> list[dict[str, str]]:
    """Decode the original MySQL CREATE TABLE statements without external I/O."""
    return json.loads(
        gzip.decompress(base64.b85decode("".join(_COMPRESSED_LEGACY_TABLES))).decode("utf-8")
    )


def upgrade() -> None:
    """Create every legacy domain table that is not already owned by the clean server."""
    for definition in _table_definitions():
        # MySQL DDL is non-transactional. IF NOT EXISTS allows a rerun to skip
        # tables successfully created before an earlier failure.
        ddl = definition["ddl"].replace("CREATE TABLE `", "CREATE TABLE IF NOT EXISTS `", 1)
        op.execute(ddl)


def downgrade() -> None:
    """Drop only the legacy domain tables in reverse dependency order."""
    for definition in reversed(_table_definitions()):
        op.execute(f"DROP TABLE IF EXISTS `{definition['name']}`")
