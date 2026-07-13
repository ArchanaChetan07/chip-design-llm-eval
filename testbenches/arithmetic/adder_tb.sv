// testbenches/arithmetic/adder_tb.sv
// Self-checking reference testbench. Prints SIM_PASS / SIM_FAIL, which
// eval/sim_runner.py parses to determine correctness.
`timescale 1ns/1ps
module tb;
    localparam WIDTH = 8;
    logic [WIDTH-1:0] a, b;
    logic [WIDTH:0]   sum;
    integer errors;
    integer i;

    adder #(.WIDTH(WIDTH)) dut (.a(a), .b(b), .sum(sum));

    task check(input [WIDTH-1:0] av, input [WIDTH-1:0] bv);
        logic [WIDTH:0] expected;
        begin
            a = av; b = bv;
            #1;
            expected = av + bv;
            if (sum !== expected) begin
                $display("MISMATCH: a=%0d b=%0d got=%0d expected=%0d", av, bv, sum, expected);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        errors = 0;

        // Directed edge cases
        check(8'd0, 8'd0);
        check(8'd255, 8'd1);      // overflow -> must set carry bit
        check(8'd255, 8'd255);    // max overflow
        check(8'd128, 8'd128);    // overflow at mid-range
        check(8'd1, 8'd0);

        // Randomized sweep
        for (i = 0; i < 200; i = i + 1) begin
            check($urandom_range(0,255), $urandom_range(0,255));
        end

        if (errors == 0)
            $display("SIM_PASS");
        else
            $display("SIM_FAIL: %0d mismatches", errors);

        $finish;
    end
endmodule
