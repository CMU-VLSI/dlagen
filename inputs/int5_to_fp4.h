#pragma hls_design ccore
ac_int<4, true> int5_to_fp4(
    ac_int<5, true> a) {

    ac_int<5, true> a_abs;
    if (a[4]) {
        a_abs = a * -1;
    } else {
        a_abs = a;
    }

    ac_int<2, false> exp;
    ac_int<1, false> mant;
    if (a_abs[3]) {
        exp = 3;
        if (a_abs[1] && a_abs[0]) {
            mant = 1;
        } else {
            mant = a_abs[2];
        }
    } else if (a_abs[2]) {
        if (a_abs[1] && a_abs[0]) {
            exp = 3;
            mant = 0;
        } else {
            exp = 2;
            mant = a_abs[1];
        }
    } else if (a_abs[1]) {
        exp = 1;
        mant = a_abs[0];
    } else if (a_abs[0]) {
        exp = 0;
        mant = 1;
    } else {
        exp = 0;
        mant = 0;
    }

    ac_int<4, true> c;
    c.set_slc(3, a.template slc<1>(4));
    c.set_slc(1, exp);
    c.set_slc(0, mant);
    
    return c;
}