// testbenches/peripherals/uart_tx_tb.sv
// Self-checking reference testbench for uart_tx.
// Captures tx by polling `busy`, rather than assuming a fixed number of
// clock edges between tx_start and each bit -- this makes the testbench
// robust to small (still-correct) latency differences in how a DUT author
// chooses to structure IDLE->START transitions, instead of over-fitting to
// one specific state machine's timing.
`timescale 1ns/1ps
module tb;
    logic clk = 0, rst_n = 0, tx_start = 0;
    logic [7:0] data;
    logic tx, busy;
    integer errors = 0;

    uart_tx dut (.clk(clk), .rst_n(rst_n), .tx_start(tx_start),
                 .data(data), .tx(tx), .busy(busy));

    always #5 clk = ~clk;

    logic captured_bits [0:9];   // start + 8 data + stop
    integer n_captured;
    integer i;
    logic busy_prev;

    task send_and_check(input [7:0] test_data);
        begin
            n_captured = 0;
            @(posedge clk); #1;
            data = test_data;
            tx_start = 1;
            @(posedge clk); #1;
            tx_start = 0;
            busy_prev = busy;

            // Capture tx on every clock edge from when busy first goes high
            // until it drops low again. Cap iterations as a timeout guard.
            for (i = 0; i < 200 && n_captured < 10; i = i + 1) begin
                @(posedge clk); #1;
                if (busy || busy_prev) begin
                    captured_bits[n_captured] = tx;
                    n_captured = n_captured + 1;
                end
                busy_prev = busy;
            end

            if (n_captured < 10) begin
                $display("MISMATCH: data=%0d timed out capturing bits, got only %0d", test_data, n_captured);
                errors = errors + 1;
            end else begin
                if (captured_bits[0] !== 1'b0) begin
                    $display("MISMATCH: data=%0d expected start bit 0, got %b", test_data, captured_bits[0]);
                    errors = errors + 1;
                end
                for (i = 0; i < 8; i = i + 1) begin
                    if (captured_bits[1+i] !== test_data[i]) begin
                        $display("MISMATCH: data=%0d bit %0d expected=%b got=%b",
                                 test_data, i, test_data[i], captured_bits[1+i]);
                        errors = errors + 1;
                    end
                end
                if (captured_bits[9] !== 1'b1) begin
                    $display("MISMATCH: data=%0d expected stop bit 1, got %b", test_data, captured_bits[9]);
                    errors = errors + 1;
                end
            end

            // idle settle before next transaction
            repeat (3) @(posedge clk);
        end
    endtask

    initial begin
        rst_n = 0; data = 8'h00; tx_start = 0;
        repeat (3) @(posedge clk);
        rst_n = 1;
        repeat (2) @(posedge clk);

        send_and_check(8'hA5);
        send_and_check(8'h00);
        send_and_check(8'hFF);
        send_and_check(8'h01);
        send_and_check(8'h80);

        if (errors == 0)
            $display("SIM_PASS");
        else
            $display("SIM_FAIL: %0d mismatches", errors);

        $finish;
    end

    // safety timeout
    initial begin
        #200000;
        $display("SIM_FAIL: timeout");
        $finish;
    end
endmodule
